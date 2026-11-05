"""Bounded component checks; no benchmark answers or model calls are used."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import httpx

ROOT=Path(__file__).resolve().parents[1]
QUERIES=[('english','Python 3.13 release date official'),
         ('chinese','嫦娥六号 返回 日期 国家航天局'),
         ('named_entity','Vera Rubin Observatory first look June 2025'),
         ('site_limited','site:who.int malaria report 2025'),
         ('pdf','IPCC AR6 synthesis report filetype:pdf'),
         ('two_clues','Nobel Prize 2024 physics Hopfield Hinton institutions')]


def main():
    out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'search':[],'browser':[]}
    for label,query in QUERIES:
        p=subprocess.run([sys.executable,str(ROOT/'Pool/resources/tools/script/searxng_search.py'),query,'--limit','5','--timeout-ms','20000'],capture_output=True,text=True,timeout=55)
        try: data=json.loads(p.stdout)
        except ValueError: data={}
        report['search'].append({'category':label,'return_code':p.returncode,'status':data.get('status'),
            'error':re.sub(r'https?://[^\s]+','[url]',str(data.get('message','')))[:240],
            'result_count':data.get('result_count',0),'records':[{k:r.get(k) for k in ['title','url','engine']} for r in data.get('records',[])]})
        print(json.dumps({k:v for k,v in report['search'][-1].items() if k!='records'}),flush=True)
    base=os.environ['SGAR_BROWSER_BASE_URL']; headers={'Authorization':'Bearer '+os.environ['SGAR_BROWSER_TOKEN']}
    with httpx.Client(trust_env=False,timeout=60) as c:
        for label,url in [('static','https://example.com'),('documentation','https://docs.python.org/3.13/whatsnew/3.13.html'),('javascript','https://demo.playwright.dev/todomvc/')]:
            data=c.post(base+'/read',headers=headers,json={'url':url}).json()
            row={'kind':label,'url':url,'status':data.get('status'),'error':data.get('error'),'title':data.get('title'),
                 'text_chars':len(data.get('text','')),'total_links':data.get('total_links'), 'page_id':data.get('page_id')}
            report['browser'].append(row); print(json.dumps(row),flush=True)
            if label=='documentation' and data.get('status')=='success':
                links=data.get('links',[])
                target=next((x['url'] for x in links if x['url'].startswith('https://docs.python.org/') and x['url']!=url),None)
                if target:
                    child=c.post(base+'/read',headers=headers,json={'url':target}).json()
                    report['browser'].append({'kind':'follow_returned_link','url':target,'status':child.get('status'),'error':child.get('error'),'title':child.get('title')})
                offset=data.get('next_text_offset')
                if offset is not None:
                    chunk=c.post(base+'/read',headers=headers,json={'url':url,'text_offset':offset}).json()
                    report['pagination']={'same_page_id':chunk.get('page_id')==data['page_id'],'next_chunk_chars':len(chunk.get('text',''))}
        bad=c.post(base+'/read',headers=headers,json={'url':'http://127.0.0.1/'}).json()
        report['private_url_rejected']=bad.get('status')=='error'
        report['missing_auth_rejected']=c.get(base+'/health').status_code==401
    report['search_nonempty']=sum(x['result_count']>0 for x in report['search'])
    report['browser_passed']=sum(x['status']=='success' for x in report['browser'])
    report['scope']='component checks, not benchmark accuracy or full search coverage'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['private_url_rejected'] or not report['missing_auth_rejected']: raise SystemExit(2)
    if not report['search_nonempty'] or report['browser_passed']<4: raise SystemExit(3)
    if not report.get('pagination',{}).get('same_page_id'): raise SystemExit(4)


if __name__=='__main__': main()
