from scripts.issue_tracker import read_tracker


def test_epic_summary_is_optional_and_refreshes_from_markdown(tmp_path):
    epic = tmp_path / '.scratch' / 'example'
    epic.mkdir(parents=True)
    (epic / 'map.md').write_text('# Example\n\nStatus: resolved\n')
    assert read_tracker(tmp_path)['epics'][0]['summary'] is None
    summary = epic / 'summary.md'
    summary.write_text('# Results\n\n## Conclusion\n\nInconclusive.\n')
    result = read_tracker(tmp_path)['epics'][0]['summary']
    assert result == {
        'source': '.scratch/example/summary.md',
        'body': summary.read_text(),
    }
    summary.write_text('# Results\n\n## Conclusion\n\nUpdated evidence.\n')
    assert 'Updated evidence.' in read_tracker(tmp_path)['epics'][0]['summary']['body']
