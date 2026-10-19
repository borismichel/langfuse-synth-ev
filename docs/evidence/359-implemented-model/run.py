"""Real provider verification of the implemented kit; no Langfuse UI claims."""
import concurrent.futures,datetime,json,os,subprocess
from pathlib import Path
from synth.agent import GrantRule,parse_decision
from synth.models import Application
from synth.policy import policy_variables
from synth.seed.prompts import chat_prompt,decision_schema
from langfuse_synth_core.companion.llm import LLMClient
ROOT=Path(__file__).parent
cases=json.loads((ROOT/'simulation/native-ui-assets/dataset-items.json').read_text())
rule=GrantRule(effective_date='2026-10-12')
out=ROOT/('kit-model-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir()
jobs=[]
for row in cases:
 data=json.loads(row['input']['application']); data['application_date']='2026-10-11' if row['id']=='before_effective' else '2026-10-12'
 # Preserve the accepted fixture's before-date control independent of its case label.
 original=json.loads(row['input']['application'])['application_date']
 if original<'2026-10-01':data['application_date']='2026-10-11'
 data['applicant_id']='rehearsal_'+row['id']
 app=Application.model_validate(data)
 variables=policy_variables(app,rule)
 for repeat in range(5 if row['id']=='eligible_flip' else 1):
  for label in ['v1','v2']:
   messages=chat_prompt(label)
   for m in messages:
    for key,value in variables.items():m['content']=m['content'].replace('{{'+key+'}}',value)
   jobs.append({'case':row['id'],'variant':label,'repetition':repeat+1,'input':variables,'expected':row['expected_output'],'messages':messages})
(out/'manifest.json').write_text(json.dumps({'source_commit':'ecd8f59f5aab0ba5511e23191906855aaf556ddb','core_commit':'8372f442e51e12234cb8b18ebd73c01b6cf0ff5a','model':'claude-sonnet-4-6','max_tokens':512,'schema':decision_schema(),'rule':rule.__dict__,'jobs':jobs,'scope':'Real provider calls using implemented kit templates/policy/core; not a native UI run.'},indent=2))
def execute(job):
 try:
  llm=LLMClient('anthropic','claude-sonnet-4-6')
  r=llm.complete(system=job['messages'][0]['content'],messages=job['messages'][1:],max_tokens=512,response_schema=decision_schema())
  app=Application.from_input(job['input']); parsed=parse_decision(r.text,app).model_dump()
  fields=['decision','list_price_eur','applied_grant_eur','financed_principal_eur','approved_line_eur']
  return {**job,'output':r.text,'parsed':parsed,'input_tokens':r.input_tokens,'output_tokens':r.output_tokens,'valid':True,'policy_correct':all(parsed[k]==job['expected'][k] for k in fields)}
 except Exception as e:return {**job,'valid':False,'error_type':type(e).__name__,'error':str(e)}
rows=[]
with (out/'responses.jsonl').open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(execute,jobs):
  f.write(json.dumps(result)+'\n');f.flush();rows.append(result)
  print(f"{len(rows)}/{len(jobs)} {result['case']} {result['variant']} valid={result['valid']} policy_correct={result.get('policy_correct')}",flush=True)
summary={'total':len(rows),'valid':sum(r['valid'] for r in rows),'by_variant':{v:{'total':sum(r['variant']==v for r in rows),'policy_correct':sum(r['variant']==v and r.get('policy_correct',False) for r in rows)} for v in ['v1','v2']}}
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(out,flush=True);print(json.dumps(summary),flush=True)
