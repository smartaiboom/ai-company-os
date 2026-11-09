"""Versioned strict schemas for existing autonomous role contracts, no business rules."""
from autonomous_company import require


def obj(**properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def arr(item):return {'type':'array','items':item}
def enum(*values):return {'type':'string','enum':list(values)}
S={'type':'string'}
CHECK=obj(criterion_id=S,status=enum('met','unmet','unknown'),evidence=S,source=enum('model_claim'))
OP={'type':['string','null'],'enum':[None,'external_data','budget','external_permission']}
HALT=obj(action=enum('stop','needs_operational_permission'),rationale=S,uncertainty=S,operation=OP)
SCHEMAS={
 'plan':{'anyOf':[
     obj(tasks=arr(obj(id=S,title=S,role=S,instructions=S,depends_on=arr(S),criteria_ids=arr(S))),
         criteria=arr(obj(id=S,description=S)),rationale=S,uncertainty=S),HALT]},
 'execute':obj(content=S,evidence=S,uncertainty=S),
 'review':obj(action=enum('accept','revise','stop','needs_operational_permission'),rationale=S,evidence=S,
              uncertainty=S,checks=arr(CHECK),feedback=S,operation=OP),
 'finalize':obj(action=enum('deliver','stop'),content=S,rationale=S,uncertainty=S,checks=arr(CHECK))}


def response_format(phase):
    require(phase in SCHEMAS,'invalid_role_phase')
    return {'type':'json_schema','json_schema':{'name':'company_'+phase+'_v1','strict':True,
                                               'schema':obj(result=SCHEMAS[phase])}}


def matches(value,schema):
    """Validate only the small JSON Schema subset emitted above; no coercion."""
    if 'anyOf' in schema:return any(matches(value,s) for s in schema['anyOf'])
    kinds=schema['type'];kinds=[kinds] if isinstance(kinds,str) else kinds
    kind=('null' if value is None else 'string' if isinstance(value,str) else
          'object' if isinstance(value,dict) else 'array' if isinstance(value,list) else 'unsupported')
    if kind not in kinds or 'enum' in schema and value not in schema['enum']:return False
    if kind=='object':
        return set(value)==set(schema['required']) and all(matches(value[k],s) for k,s in schema['properties'].items())
    if kind=='array':return all(matches(v,schema['items']) for v in value)
    return True
