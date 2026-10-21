import json

from scripts.issue_tracker import read_tracker


def test_narrative_file_takes_precedence_and_retains_explanatory_fields(tmp_path):
    run = tmp_path / 'results' / 'run'
    run.mkdir(parents=True)
    (run / 'manifest.json').write_text(json.dumps({'stage': 'research', 'status': 'running'}))
    entry = {'id': 'finding', 'at': '2026-10-21T13:00:00+00:00', 'title': 'Long-gap baseline',
             'detail': 'A grouped update.', 'testing': 'Can both models finish?',
             'why': 'Separate runtime from interval precision.', 'observed': 'Two timeouts.',
             'meaning': 'Cause not isolated yet.', 'next': 'Profile the failed pair.'}
    (run / 'activity.json').write_text(json.dumps({'entries': [dict(entry, id='raw')]}))
    (run / 'narrative.json').write_text(json.dumps({'entries': [entry]}))
    result = read_tracker(tmp_path)['campaign']['activity']
    assert len(result) == 1 and result[0]['id'] == 'finding'
    for key in ['testing', 'why', 'observed', 'meaning', 'next']:
        assert result[0][key] == entry[key]


def test_invalid_narrative_field_is_omitted_with_warning(tmp_path):
    run = tmp_path / 'results' / 'run'
    run.mkdir(parents=True)
    (run / 'manifest.json').write_text(json.dumps({'stage': 'research', 'status': 'running'}))
    entry = {'id': 'bad', 'at': '2026-10-21T13:00:00+00:00', 'title': 'Bad',
             'detail': 'Bad field.', 'meaning': {'unsupported': 'structure'}}
    (run / 'narrative.json').write_text(json.dumps({'entries': [entry]}))
    campaign = read_tracker(tmp_path)['campaign']
    assert campaign['activity'] == []
    assert any('narrative.json' in warning for warning in campaign['warnings'])
