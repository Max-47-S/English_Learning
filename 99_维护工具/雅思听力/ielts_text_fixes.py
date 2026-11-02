"""Idempotent corrections verified against the printed two-column PDF table."""
GROUP = 'c11-s4-phrases'
ALIASES = {GROUP + '-0447': GROUP + '-0445', GROUP + '-0456': GROUP + '-0454'}


def fix_wrapped_phrases(data):
    entries = data['entries']
    by_id = {e['id']: e for e in entries}
    fixes = [('-0445', 'rubber-wood furniture business', '橡胶木家具生意'),
             ('-0454', 'digital marketing service providers', '数字营销服务提供商')]
    for suffix, word, meaning in fixes:
        if GROUP + suffix in by_id:
            by_id[GROUP + suffix].update(word=word, meaning=meaning,
                reviewNote='已按原 PDF 第 69 页合并同一表格单元格内的换行。')
    entries[:] = [e for e in entries if e['id'] not in ALIASES]
    # Wrapped cells made the OCR baselines disagree with the printed row order.
    for left, right in [('-0449', '-0448'), ('-0451', '-0450'), ('-0453', '-0452'), ('-0455', '-0454')]:
        ids = {e['id']: i for i, e in enumerate(entries)}
        a, b = ids[GROUP + left], ids[GROUP + right]
        if a > b:
            entries[a], entries[b] = entries[b], entries[a]
    order = 0
    for entry in entries:
        if entry['group'] == GROUP:
            order += 1
            entry['order'] = order
    groups = data.get('groups', []) + [g for chapter in data.get('chapters', []) for g in chapter['groups']]
    for group in groups:
        if group['id'] == GROUP:
            group['entries'] = order
    data.setdefault('entryAliases', {}).update(ALIASES)
    return data
