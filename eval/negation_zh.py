# 同一段 state 問 Q 與「反向 Q」，理想上 P(是|Q)+P(是|反Q)≈1；偏離代表系統性偏「是」或偏「否」
import json, subprocess, os
D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic")
from common import JEV, RESULTS
items=[json.loads(l) for l in open(os.path.join(D,'pairs_zh.jsonl')) if not l.startswith('//')]
NEG={"顧客是否要求退款？":"顧客是否沒有要求退款？","這則訊息是否為投訴？":"這則訊息是否不是投訴？","這則新聞是否與台灣相關？":"這則新聞是否與台灣無關？",
"這則新聞是否為中國大陸的新聞？":"這則新聞是否不是中國大陸的新聞？","這段內容是否可能為詐騙？":"這段內容是否不太可能是詐騙？",
"照主管的排法，是否違反公司規定？":"照主管的排法，是否符合公司規定？","這則新聞的發布者是否為中國大陸的政府或機構？":"這則新聞的發布者是否不是中國大陸的政府或機構？",
"醫師是否要求寶寶住院？":"醫師是否沒有要求寶寶住院？"}
rows=[]
for it in items:
    if it['type']!='noul': continue
    qs={"pos":{"type":"noul","instructions":it['instructions']},"neg":{"type":"noul","instructions":NEG[it['instructions']]}}
    out=subprocess.run([JEV,"ask","-"],input=json.dumps({"state":it['state'],"questions":qs},ensure_ascii=False),capture_output=True,text=True)
    a=json.loads(out.stdout)['answers']; p=a['pos']['noul']; n=a['neg']['noul']
    rows.append({"id":it['id'],"expected":it['expected'],"P_yes_Q":round(p,3),"P_yes_negQ":round(n,3),"sum":round(p+n,3),
                 "neg_correct":(n>=0.5)==(not it['expected'])})
    print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
json.dump(rows,open(os.path.join(RESULTS,'negation_rows.json'),'w'),ensure_ascii=False,indent=1)
print('neg-question correct:',sum(r['neg_correct'] for r in rows),'/',len(rows))
print('mean |sum-1|:',round(sum(abs(r['sum']-1) for r in rows)/len(rows),3))
