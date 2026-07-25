import importlib.util
from pathlib import Path

def _load_generate():
    path = Path(__file__).parents[1] / 'scripts' / 'generate.py'
    spec = importlib.util.spec_from_file_location('generate_backfill_test', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class Index:
    safe_story_ids = {'story-1','story-2'}
    def resolve(self,item): return {'one':'story-1','two':'story-2'}.get(item.get('slug'),'')

def test_backfill_persists_exact_safe_identity(tmp_path):
    g=_load_generate(); rows,report=g._backfill_archive_editorial_story_ids([{'slug':'one','headline':'One'},{'slug':'unknown','headline':'Unknown'}],Index(),tmp_path)
    assert rows[0]['editorial_story_id']=='story-1'; assert report['resolved']==1; assert report['unmatched']==1
    assert (tmp_path/'data'/'archive-identity-backfill.json').exists()

def test_backfill_never_collapses_custom_recurring_reports(tmp_path):
    g=_load_generate(); rows,report=g._backfill_archive_editorial_story_ids([{'slug':'one','headline':'Weekly traffic report','is_custom':True}],Index(),tmp_path)
    assert 'editorial_story_id' not in rows[0]; assert report['custom_isolated']==1

def test_existing_safe_identity_is_preserved(tmp_path):
    g=_load_generate(); rows,report=g._backfill_archive_editorial_story_ids([{'slug':'one','headline':'One','editorial_story_id':'story-1'}],Index(),tmp_path)
    assert rows[0]['editorial_story_id']=='story-1'; assert report['already_identified']==1
