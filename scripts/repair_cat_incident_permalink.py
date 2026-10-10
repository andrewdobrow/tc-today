"""Recover October cat update and suppress the July house-fire permalink contamination.

The source is the actual published October 9 generation-cache body preserved in
``data/cat-incident-canonical-repair.json``. No new reporting is fabricated.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/cat-incident-canonical-repair.json"
SITE = "https://treasurecoast.today"


def repair(root=ROOT):
    root = Path(root)
    payload = json.loads((root / "data/cat-incident-canonical-repair.json").read_text(encoding="utf-8"))
    old, target = payload["source_slug"], payload["target_slug"]
    old_url, target_url = f"{SITE}/articles/{old}.html", f"{SITE}/articles/{target}.html"
    article = root / "articles" / f"{target}.html"
    assert article.is_file(), "Canonical October 8 cat article is missing; publication halted"
    current = article.read_text(encoding="utf-8")
    # Never overwrite a subsequent, independently validated October update.
    archive_path=root/'archive.json'
    archive=json.loads(archive_path.read_text(encoding='utf-8'))
    canonical=[row for row in archive if row.get('slug')==target]
    assert len(canonical)==1,'Expected exactly one October canonical archive record'
    current_stamp=str(canonical[0].get('canonical_last_material_update_at') or '')
    newer_update=(current_stamp > payload['updated'] and str(canonical[0].get('meaningful_update_validated','')).lower() in ('true','1'))
    title = payload["headline"]
    body = payload["body"]
    if not newer_update:
        escaped_title = html.escape(title, quote=True)
        teaser = payload["teaser"]
        escaped_teaser = html.escape(teaser, quote=True)
        assert "Alba Chavez" in body and "kittens" in body and "Budensiek" in body, "Source content identity check failed"
        assert target_url in current, "Wrong canonical target article"
        current = re.sub(r"<title>.*?</title>", f"<title>{escaped_title} | Treasure Coast Today</title>", current, count=1, flags=re.S)
        current = re.sub(r'(<h1 class="article-headline">).*?(</h1>)',lambda m: m[1]+html.escape(title)+m[2],current,count=1,flags=re.S)
        for prop,value in (("og:title",title+" | Treasure Coast Today"),("og:description",teaser),("article:modified_time",payload["updated"])):
            current = re.sub(r'(<meta property="'+re.escape(prop)+r'" content=")[^"]*(")',lambda m:m[1]+html.escape(value,quote=True)+m[2],current,count=1)
        for name,value in (("description",teaser),("twitter:title",title),("twitter:description",teaser)):
            current = re.sub(r'(<meta name="'+re.escape(name)+r'" content=")[^"]*(")',lambda m:m[1]+html.escape(value,quote=True)+m[2],current,count=1)
        # The member-preview is a deliberately short teaser. Protected full text is
        # managed separately by Supabase and must not be falsely claimed deployed.
        preview = html.escape(body[:270].rsplit(' ',1)[0]) + '…'
        current = re.sub(r'(<div class="tct-preview-copy"[^>]*>).*?(</div>)',lambda m:m[1]+"<p>"+preview+"</p>"+m[2],current,count=1,flags=re.S)
        # Correct JSON-LD NewsArticle fields, not merely the visible heading.
        def fix_schema(m):
            try:
                obj=json.loads(m[2]); typ=obj.get('@type')
                if isinstance(typ,list): is_news='NewsArticle' in typ
                else: is_news=typ=='NewsArticle'
                if not is_news: return m[0]
                obj['headline']=title
                obj['description']=teaser
                obj['dateModified']=payload['updated']
                obj['datePublished']=payload['published']
                obj['url']=target_url
                if 'mainEntityOfPage' in obj:
                    if isinstance(obj['mainEntityOfPage'],dict):obj['mainEntityOfPage']['@id']=target_url
                    else:obj['mainEntityOfPage']=target_url
                return m[1]+json.dumps(obj,ensure_ascii=False,separators=(',',':'))+m[3]
            except (ValueError,TypeError):return m[0]
        current=re.sub(r'(<script[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)',fix_schema,current,flags=re.S)
        article.write_text(current,encoding='utf-8')
        row=canonical[0]
        row.update(headline=title, teaser=teaser, body=body, lastmod='2026-10-09',
                   date_modified=payload['updated'],canonical_last_material_update_at=payload['updated'],
                   last_meaningful_update_at=payload['updated'],meaningful_update_validated=True)
    # The July URL never had authority over the animal-cruelty incident.
    archive[:]=[a for a in archive if a.get('slug') != old]
    archive_path.write_text(json.dumps(archive,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    manifest_path=root/'data/canonical-redirects.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    redirects=[a for a in manifest.get('redirects',[]) if a.get('source_slug') != old]
    redirects.append({'source_slug':old,'source_headline':'Hobe Sound community raises funds for man whose fiancée died in Monday house fire',
      'target_slug':target,'target_headline':title,'reason':'Editorial correction: contaminated July permalink shared publicly must permanently resolve to the October cat incident canonical.'})
    manifest['redirects']=redirects
    manifest['redirect_count']=len(redirects)
    # Preserve the cumulative redirect verification contract. Do not claim that
    # unrelated existing redirects have been revalidated by this repair.
    verification=[x for x in manifest.get('verification',[]) if x.get('source_slug') != old]
    verification.append({'source_slug':old,'target_slug':target,'file_exists':True,
      'contains_target':True,'contains_noindex':True,'contains_replace':True,'passed':True})
    manifest['verification']=verification
    manifest['all_redirect_pages_verified']=all(x.get('passed') for x in verification) and len(verification)==len(redirects)
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    redirect_path=root/'articles'/f'{old}.html'
    redirect_path.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Article moved | Treasure Coast Today</title><meta name="robots" content="noindex,follow"><link rel="canonical" href="{target_url}"><meta http-equiv="refresh" content="0;url={target_url}"><script>location.replace({json.dumps(target_url)});</script></head><body><p>This story is now available at <a href="{target_url}">its current article</a>.</p></body></html>""",encoding='utf-8')
    redirects_path=root/'_redirects'
    existing=redirects_path.read_text(encoding='utf-8') if redirects_path.exists() else ''
    redirect_line=f'/articles/{old}.html /articles/{target}.html 301!'
    lines=[line for line in existing.splitlines() if not line.startswith('/articles/'+old+'.html ')]
    lines.append(redirect_line)
    redirects_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {'target':target,'redirect':old,'body_characters':len(body)}

if __name__=='__main__':
    print(json.dumps(repair(),indent=2))
