"""Native Gemini wire boundary; no sending, retrying, keys in URLs, or billing."""
from copy import deepcopy
import json
from urllib.request import Request
from ai_provider_adapter import ProviderSpec, response_metadata
from autonomous_company import require, exact, digest, parse
from role_json_schema import response_format

MODEL='gemini-3.1-flash-lite'
ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent'
COST_POLICY={'basis':'owner_verified_free_tier_and_official_model_pricing',
             'max_cost':0,'paid_fallback':False,'automatic_retry':False,
             'pricing_source':'https://aistudio.google.com/docs/pricing#gemini-3.1-flash-lite',
             'rate_limits_source':'https://aistudio.google.com/docs/rate-limits',
             'verified_date_kst':'2026-11-04','response_cost_required':False}


class GeminiFreeAdapter:
    spec=ProviderSpec('gemini_free',MODEL,'generate_content',ENDPOINT,'x-goog-api-key',4096,
                      'verified_free_tier_only',enabled=False)

    def build_request(self,body,api_key):
        require(isinstance(api_key,str) and bool(api_key.strip()) and len(api_key)<=4096
                and '\r' not in api_key and '\n' not in api_key,'missing_gemini_key')
        return Request(self.spec.base_url,data=body,method='POST',
                       headers={'Content-Type':'application/json','x-goog-api-key':api_key})

    def response_metadata(self,response):return response_metadata(self.normalize(response))

    def prepare_payload(self,payload):
        message=json.loads(payload['messages'][1]['content']);phase=message['phase']
        message['output_contract']={'result':message['output_contract']}
        return {'systemInstruction':{'parts':[{'text':payload['messages'][0]['content']+
                    ' Return only JSON wrapped in result. Keep values concise within 4096 output tokens.'}]},
                'contents':[{'role':'user','parts':[{'text':json.dumps(message,ensure_ascii=False)}]}],
                'generationConfig':{'maxOutputTokens':4096,'temperature':0.2,
                    'responseMimeType':'application/json',
                    'responseJsonSchema':deepcopy(response_format(phase)['json_schema']['schema'])}}

    def validate_payload(self,payload,phase):
        exact(payload,('systemInstruction','contents','generationConfig'))
        config=payload['generationConfig']
        exact(config,('maxOutputTokens','temperature','responseMimeType','responseJsonSchema'))
        require(type(config['maxOutputTokens']) is int and config['maxOutputTokens']==4096
                and config['temperature']==0.2 and config['responseMimeType']=='application/json'
                and digest(config['responseJsonSchema'])==digest(response_format(phase)['json_schema']['schema']),
                'gemini_payload_policy')
        exact(payload['systemInstruction'],('parts',))
        require(isinstance(payload['systemInstruction']['parts'],list)
                and len(payload['systemInstruction']['parts'])==1,'gemini_payload_policy')
        exact(payload['systemInstruction']['parts'][0],('text',))
        require(isinstance(payload['systemInstruction']['parts'][0]['text'],str),'gemini_payload_policy')
        require(isinstance(payload['contents'],list) and len(payload['contents'])==1,'gemini_payload_policy')
        content=payload['contents'][0];exact(content,('role','parts'))
        require(content['role']=='user' and isinstance(content['parts'],list) and len(content['parts'])==1,'gemini_payload_policy')
        exact(content['parts'][0],('text',));message=parse(content['parts'][0]['text'])
        require(message['phase']==phase,'gemini_payload_phase')

    def normalize(self,envelope):
        """Translate only validated final text; thought/tool/safety blocks never become work."""
        require(isinstance(envelope,dict),'invalid_response_envelope')
        require('error' not in envelope,'gemini_error_envelope')
        feedback=envelope.get('promptFeedback',{})
        require(isinstance(feedback,dict) and not feedback.get('blockReason'),'provider_refusal')
        candidates=envelope.get('candidates')
        require(isinstance(candidates,list) and len(candidates)==1 and isinstance(candidates[0],dict),'invalid_choices')
        candidate=candidates[0]
        require(candidate.get('finishReason')=='STOP','incomplete_response')
        require(not candidate.get('refusal') and not any(r.get('blocked') is True
                for r in candidate.get('safetyRatings',[]) if isinstance(r,dict)),'provider_refusal')
        content=candidate.get('content');require(isinstance(content,dict) and content.get('role')=='model','invalid_response_envelope')
        parts=content.get('parts');require(isinstance(parts,list) and bool(parts),'invalid_response_envelope')
        texts=[]
        for part in parts:
            require(isinstance(part,dict),'invalid_response_envelope')
            require(not any(k in part for k in ('functionCall','executableCode','codeExecutionResult','inlineData','fileData')),'unexpected_tools')
            if part.get('thought') is True:continue
            require('thought' not in part or part['thought'] is False,'invalid_response_envelope')
            require(isinstance(part.get('text'),str),'invalid_response_envelope')
            texts.append(part['text'])
        raw=''.join(texts);require(bool(raw.strip()) and len(raw.encode())<=131072,'invalid_response_envelope')
        usage=envelope.get('usageMetadata');require(isinstance(usage,dict),'gemini_usage_unverified')
        if 'cost' in usage:
            require(type(usage['cost']) in (int,float) and usage['cost']==0,'gemini_unexpected_cost')
        tokens={}
        for src,dest in (('promptTokenCount','prompt_tokens'),('candidatesTokenCount','completion_tokens'),('totalTokenCount','total_tokens')):
            val=usage.get(src)
            require(type(val) is int and 0<=val<=1000000000,'gemini_usage_unverified')
            tokens[dest]=val
        thought_tokens=usage.get('thoughtsTokenCount',0)
        require(type(thought_tokens) is int and thought_tokens>=0,'gemini_usage_unverified')
        require(tokens['completion_tokens']+thought_tokens<=4096
                and tokens['total_tokens']>=tokens['prompt_tokens']+tokens['completion_tokens']+thought_tokens,
                'gemini_usage_invalid')
        return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':raw}}], 'usage':tokens}
