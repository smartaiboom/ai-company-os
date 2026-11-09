"""Fictional role outputs. These examples are not production decision rules."""
import json
from autonomous_company import MockManagerProvider, MockEmployeeProvider, digest


class FictionalModels:
    def __init__(self, domain='library', *, revise=False, always_revise=False, unknown=False, fail=False):
        self.domain=domain;self.revise=revise;self.always_revise=always_revise;self.unknown=unknown;self.fail=fail
        self.calls=[];self.contexts=[]
        self.manager=MockManagerProvider('fixture-manager-'+domain,self.manager_response)
        self.employee=MockEmployeeProvider('fixture-employee-'+domain,self.employee_response)

    def manager_response(self,phase,ctx):
        self.calls.append(('manager',phase));self.contexts.append((phase,ctx))
        if phase=='plan':
            library='도서관' in ctx['goal']
            criteria=[{'id':'audience' if library else 'owner','description':'도서관 이용 순서가 구체적으로 설명된다' if library else '재고 확인 담당자와 일일 절차가 명시된다'},
                      {'id':'uncertain','description':'확인하지 않은 외부 사실을 미확인으로 구분한다'}]
            first,second=('observe','guide') if library else ('baseline','handoff')
            value={'rationale':ctx['goal']+'에 필요한 조사와 작성 업무를 배분합니다.','uncertainty':'실제 현장 확인은 하지 않았습니다.',
                   'criteria':criteria,'tasks':[
                {'id':first,'title':'이용 자료 조사' if library else '재고 절차 조사','role':'조사 담당',
                 'instructions':ctx['goal']+'의 기초 자료를 정리하고 미확인 항목을 표시하세요.', 'depends_on':[], 'criteria_ids':[c['id'] for c in criteria]},
                {'id':second,'title':'이용 안내 작성' if library else '인수인계 안내 작성','role':'안내 작성 담당',
                 'instructions':ctx['goal']+'의 선행 조사 결과를 이용해 안내문을 작성하세요.', 'depends_on':[first], 'criteria_ids':[c['id'] for c in criteria]}]}
        elif phase=='review':
            needs=self.always_revise or self.revise and ctx['result']['revision']==1 and not ctx['previous_results']
            action='stop' if self.unknown else 'revise' if needs else 'accept'
            value={'action':action,'rationale':'기준별 제출 내용을 대조했습니다.','evidence':ctx['result']['content'],
                   'uncertainty':'외부 사실은 독립 검증하지 않았습니다.',
                   'checks':[{'criterion_id':c['id'],'status':'unknown' if self.unknown else 'unmet' if needs else 'met',
                              'evidence':'자료 표기와 절차를 확인했으며 현장 사실은 미확인입니다.','source':'model_claim'} for c in ctx['criteria']],
                   'feedback':'마감 담당자와 재고 확인 순서를 명시하고 미확인 주장을 표시하세요.' if needs else '', 'operation':None}
        else:
            value={'action':'deliver','content':ctx['goal']+' — 통합 안내\n\n## 배포용 안내\n'+ctx['results'][-1]['content']+'\n\n## 조사 근거\n'+ctx['results'][0]['content']+'\n\n## 검토 및 적용 한계\n각 기준의 자료 표기를 대조했습니다. 현장 규정·운영 정보는 독립 확인하지 않았으므로 배포 전 확인해야 합니다.',
                   'rationale':'수락한 직원 결과와 검토 기록을 통합했습니다.','uncertainty':'현장 적용과 외부 사실 확인은 미실시입니다.',
                   'checks':[{'criterion_id':c['id'],'status':'met','evidence':'각 직원 결과의 절차·미확인 표시를 대조했습니다.','source':'model_claim'} for c in ctx['plan']['criteria']],
                   'task_refs':[{'task_id':r['task_id'],'revision':r['revision'],'result_hash':digest(r)} for r in ctx['results']]}
        return json.dumps(value,ensure_ascii=False)

    def employee_response(self,phase,ctx):
        self.calls.append(('employee',ctx['assignment']['role']));self.contexts.append((phase,ctx))
        if self.fail:raise TimeoutError('PRIVATE')
        if ctx['revision_feedback']:
            content='마감 담당자가 매일 부족 수량을 확인하고 기록합니다. 외부 사실은 미확인입니다.'
        elif self.domain=='stock' and self.revise and not ctx['previous_results']:
            content='초안: 담당자 누락, 재고 확인 절차 보완 필요. 현장 사실 미확인.'
        elif '도서관' in ctx['goal'] and not ctx['previous_results']:
            content=('도서관 이용 자료 조사 메모 (가상 자료)\n'
                     '대상은 처음 방문하는 이용자입니다. 안내가 필요한 순서는 방문 준비, 이용 등록 확인, 자료 검색, 대출·반납 조건 확인입니다.\n'
                     '운영 시간·회원 자격·대출 기간·연장 규정은 확인하지 못했습니다. 기관의 실제 공지나 담당자 확인이 필요합니다.')
        elif '도서관' in ctx['goal']:
            content=('처음 방문하는 이용자를 위한 안내문\n'
                     '1. 방문 전 기관의 운영 시간과 준비물을 확인하세요. 현재 자료에는 확인된 운영 시간이 없습니다.\n'
                     '2. 안내 창구에서 이용 등록 조건과 회원증 발급 절차를 확인하세요.\n'
                     '3. 필요한 자료를 검색하고 소장 위치를 찾기 어려우면 직원에게 문의하세요.\n'
                     '4. 대출 전 반납 기한·연장·분실 처리 규정을 확인하세요. 구체적인 기간과 비용은 미확인입니다.\n'
                     '배포 준비: 실제 운영 정보 확인란을 채운 뒤 안내문을 사용하세요.')
        elif ctx['previous_results']:
            content=('재고 업무 인수인계 안내\n'
                     '시작: 마감 담당자는 확인할 품목 목록과 전일 기록을 준비합니다.\n'
                     '확인: 부족 수량과 확인 시각을 기록하고 누락 품목을 다시 대조합니다.\n'
                     '인계: 다음 담당자에게 미해결 품목과 확인할 자료를 전달합니다.\n'
                     '실제 품목 수량·발주 기준·담당자 이름은 미확인이므로 기관 자료로 보완해야 합니다.')
        else:
            content=('재고 기초 조사 메모\n마감 담당자가 품목별 부족 수량과 확인 시각을 기록하는 절차를 제안합니다. '
                     '실제 수량과 발주 기준은 확인하지 않았습니다.')
        if ctx['previous_results']:content+='\n선행 결과: '+'\n'.join(r['content'] for r in ctx['previous_results'])
        return json.dumps({'content':content,'evidence':'제공된 모의 자료를 정리했습니다.','uncertainty':'독립적인 출처·현장 검증은 수행하지 않았습니다.'},ensure_ascii=False)
