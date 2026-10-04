import json, subprocess, os
D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic")
from common import JEV, RESULTS
items=[json.loads(l) for l in open(os.path.join(D,'pairs_en.jsonl')) if not l.startswith('//')]
NEG={"Does the customer ask for a refund?":"Is the customer NOT asking for a refund?","Is this message a complaint?":"Is this message something other than a complaint?",
"Is this news related to Taiwan?":"Is this news unrelated to Taiwan?","Is this news from mainland China?":"Is this news not from mainland China?",
"Is this content likely a scam?":"Is this content unlikely to be a scam?","Would the manager's schedule break the company rule?":"Would the manager's schedule comply with the company rule?",
"Is the source of this news a government or agency of mainland China?":"Is the source of this news something other than a government or agency of mainland China?",
"Did the doctor require the baby to be admitted to hospital?":"Did the doctor say no hospital admission was needed?"}
rows=[]
for it in items:
    if it['type']!='noul': continue
    qs={"pos":{"type":"noul","instructions":it['instructions']},"neg":{"type":"noul","instructions":NEG[it['instructions']]}}
    out=subprocess.run([JEV,"ask","-"],input=json.dumps({"state":it['state'],"questions":qs},ensure_ascii=False),capture_output=True,text=True)
    a=json.loads(out.stdout)['answers']; p=a['pos']['noul']; n=a['neg']['noul']
    rows.append({"id":it['id'],"expected":it['expected'],"P_yes_Q":round(p,3),"P_yes_negQ":round(n,3),"sum":round(p+n,3),"neg_correct":(n>=0.5)==(not it['expected'])})
    print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
json.dump(rows,open(os.path.join(RESULTS,'negation_rows_en.json'),'w'),ensure_ascii=False,indent=1)
print('neg-question correct:',sum(r['neg_correct'] for r in rows),'/',len(rows))
print('mean |sum-1|:',round(sum(abs(r['sum']-1) for r in rows)/len(rows),3))
