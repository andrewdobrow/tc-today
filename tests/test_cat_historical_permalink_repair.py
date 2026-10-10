import json
from pathlib import Path
from scripts.repair_cat_incident_permalink import repair

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/cat-incident-canonical-repair.json').read_text())
OLD=DATA['source_slug']
NEW=DATA['target_slug']

def test_contaminated_july_url_is_redirect_and_not_archive_story():
    text=(ROOT/'articles'/f'{OLD}.html').read_text()
    assert 'location.replace(' in text
    assert f'/articles/{NEW}.html' in text
    assert 'noindex,follow' in text
    assert OLD not in {a.get('slug') for a in json.loads((ROOT/'archive.json').read_text())}
    assert f'/articles/{OLD}.html /articles/{NEW}.html 301!' in (ROOT/'_redirects').read_text()

def test_updated_october_article_keeps_published_date_and_full_body():
    page=(ROOT/'articles'/f'{NEW}.html').read_text()
    assert DATA['headline'] in page
    assert 'article:published_time" content="Thu, 08 Oct 2026' in page
    archive=json.loads((ROOT/'archive.json').read_text())
    row=next(a for a in archive if a.get('slug')==NEW)
    assert row['body']==DATA['body']
    assert row['canonical_last_material_update_at']==DATA['updated']
    assert row['canonical_first_published_at']==DATA['published']

def test_repair_is_idempotent_and_preserves_redirect_history():
    import shutil
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        root=Path(d)
        (root/'articles').mkdir()
        (root/'data').mkdir()
        for src in ['archive.json','_redirects']:
            shutil.copyfile(ROOT/src,root/src)
        for src in ['cat-incident-canonical-repair.json','canonical-redirects.json']:
            shutil.copyfile(ROOT/'data'/src,root/'data'/src)
        for s in [OLD,NEW]:
            shutil.copyfile(ROOT/'articles'/f'{s}.html',root/'articles'/f'{s}.html')
        first=repair(root)
        a=(root/'data/canonical-redirects.json').read_bytes()
        b=(root/'articles'/f'{NEW}.html').read_bytes()
        second=repair(root)
        assert first==second
        assert a==(root/'data/canonical-redirects.json').read_bytes()
        assert b==(root/'articles'/f'{NEW}.html').read_bytes()

def test_historical_house_fire_cannot_receive_animal_cruelty_update():
    import importlib.util, sys, types
    from datetime import datetime, timezone
    if 'feedparser' not in sys.modules:
        f=types.ModuleType('feedparser'); f.parse=lambda *a,**k:types.SimpleNamespace(entries=[])
        sys.modules['feedparser']=f
    if 'anthropic' not in sys.modules:
        a=types.ModuleType('anthropic'); a.Anthropic=lambda *x,**y:types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **k:None))
        sys.modules['anthropic']=a
    spec=importlib.util.spec_from_file_location('generate_cat_history_test',ROOT/'scripts/generate.py')
    g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    old = {
        'slug':OLD,
        'headline':'Hobe Sound community raises funds for man whose fiancee died in Monday house fire',
        'permalink_origin_headline':'Hobe Sound community raises funds for man whose fiancee died in Monday house fire',
        'date':'2026-07-03',
        'lastmod':'2026-07-03',
    }
    item={'headline':DATA['headline'], 'source_url':'https://example.com/kittens'}
    result=g._prospective_archive_update_alignment(item,old,now=datetime(2026,10,9,tzinfo=timezone.utc))
    assert result['aligned'] is False
    assert result['reason']=='historical_permanent_permalink_incident_conflict'
