import json

from scripts.campaign_history import read_history


def write_run(root, name, status, rows):
    folder = root / 'results' / name
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text(json.dumps({
        'stage': 'research', 'status': status, 'planned': 3, 'attempted': len(rows),
        'source_signature': 'frozen-version', 'budget_seconds': 60, 'elapsed_seconds': 20,
    }))
    (folder / 'results.json').write_text(json.dumps({'results': rows}))
    return folder


def test_recovery_is_attached_not_counted_as_another_campaign(tmp_path):
    write_run(tmp_path, 'original', 'running', [])
    recovered = write_run(tmp_path, 'recovered', 'interrupted', [
        {'status': 'success'}, {'status': 'time_limit'}, {'status': 'untested'}])
    (recovered / 'raw').mkdir()
    (recovered / 'raw/manifest.json').write_text('{"stage":"research","status":"running"}')
    (tmp_path / 'results/campaign-history.json').write_text(json.dumps({'campaigns': [{
        'id': 'original', 'title': 'Original experiment', 'source': 'results/recovered',
        'original_source': 'results/original', 'date': '2026-10-21', 'stages': [],
    }]}))
    result = read_history(tmp_path)
    assert len(result['campaigns']) == 1
    row = result['campaigns'][0]
    assert row['status'] == 'interrupted' and row['counts']['success'] == 1
    assert row['counts']['untested'] == 1 and row['source_signature'] == 'frozen-version'
    assert row['original_source'] == 'results/original'


def test_unregistered_runs_are_discovered_and_external_sources_rejected(tmp_path):
    write_run(tmp_path, 'new', 'complete', [{'status': 'success'}])
    (tmp_path / 'results/campaign-history.json').write_text(json.dumps({'campaigns': [{
        'id': 'escape', 'source': '../outside', 'title': 'Unsafe'}]}))
    result = read_history(tmp_path)
    assert any(row['source'] == 'results/new' for row in result['campaigns'])
    assert not any(row['id'] == 'escape' for row in result['campaigns'])
    assert result['warnings']


def test_additional_outcomes_are_covered_and_not_counted_twice(tmp_path):
    write_run(tmp_path, 'base', 'complete', [{'status': 'success'}])
    write_run(tmp_path, 'extra', 'complete', [{'status': 'success'}])
    (tmp_path / 'results/campaign-history.json').write_text(json.dumps({'campaigns': [{
        'id': 'base', 'title': 'Combined', 'source': 'results/base',
        'additional_outcomes': ['results/extra', 'results/extra', 'results/base'],
    }]}))
    result = read_history(tmp_path)
    assert len(result['campaigns']) == 1
    assert result['campaigns'][0]['counts']['success'] == 2
    assert result['campaigns'][0]['warnings']
