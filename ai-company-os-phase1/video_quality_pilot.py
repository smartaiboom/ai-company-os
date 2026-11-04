"""Developer-authored tool demonstration. Never a live AI company delivery."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from production_video import TOOL,render

def sample():
    return {'tool':TOOL,'width':1280,'height':720,'series':'질문을 설계하는 작은 습관 · VISUAL PILOT',
        'palette':{'background':'#10162D','surface':'#202D4C','accent':'#6CE9C5','text':'#F4F5FC'},
        'audio_mode':'none','scenes':[
        {'title':'답변의 차이는\n질문에서 시작돼요','subtitle':'막연한 질문 대신, 원하는 결과를 먼저 떠올려 보세요.',
         'narration':'원하는 결과를 먼저 생각해 보세요.','seconds':6,
         'graphic':{'kind':'conversation','labels':['무엇을 알려줄까?','원하는 결과는?','구체적으로 질문하기']},'camera':'push_in','transition':'fade'},
        {'title':'목표를\n선명하게','subtitle':'무엇을 만들고 싶은지 한 문장으로 설명해 보세요.',
         'narration':'만들고 싶은 결과를 설명해 보세요.','seconds':6,
         'graphic':{'kind':'target','labels':['한 문장으로 정리한 목표']},'camera':'pan_right','transition':'fade'},
        {'title':'상황과 형식을\n함께 알려주세요','subtitle':'목표 · 상황 · 형식. 답변이 필요한 맥락을 전달하세요.',
         'narration':'목표와 상황, 답변 형식을 알려주세요.','seconds':6,
         'graphic':{'kind':'workflow','labels':['목표','상황','형식']},'camera':'hold','transition':'cut'},
        {'title':'초안에서\n한 걸음 더','subtitle':'답변을 읽고 부족한 부분을 다시 질문하세요.',
         'narration':'답변을 읽고 질문을 보완해 보세요.','seconds':6,
         'graphic':{'kind':'comparison','labels':['처음의 질문','보완한 질문']},'camera':'push_in','transition':'fade'}]}


def main(argv=None):
    parser=argparse.ArgumentParser(description='오프라인 시각 개선 데모. 실제 AI 제작물이 아님')
    parser.add_argument('--output',required=True);parser.add_argument('--reference-voice',action='store_true')
    args=parser.parse_args(argv);folder=Path(args.output)
    folder.mkdir(parents=True,exist_ok=False)
    spec=sample()
    if args.reference_voice:spec['audio_mode']='espeak_reference'
    (folder/'spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
    receipt=render(spec,folder)
    print(json.dumps({'demo':'developer_fixture_not_live_AI','output':str(folder/'video.mp4'),
                      'duration':receipt['duration_seconds'],'audio_mode':spec['audio_mode'],'decoded':receipt['decoded']},ensure_ascii=False))


if __name__=='__main__':main()
