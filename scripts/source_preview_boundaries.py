import json
import os

def get_authoritative_boundaries():
    """
    Returns a list of 46 boundary definitions mapping the logical transitions 
    between source-preview items (Appendix 16 to the last special form).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    toc_path = os.path.join(base_dir, 'data', 'toc.json')
    rendering_path = os.path.join(base_dir, 'data', 'page-rendering.json')
    
    with open(toc_path, 'r', encoding='utf-8') as f:
        toc = json.load(f)
    with open(rendering_path, 'r', encoding='utf-8') as f:
        rendering = json.load(f)

    # We need to collect the items in order.
    # Source-preview items include:
    # 1. Appendix 16, 17, 18 (from toc['appendices'])
    # 2. All forms (from toc['forms'])
    # 3. All special forms (from toc['specialForms'])
    
    items = []
    
    # 1. Appendices
    for app in toc.get('appendices', []):
        if app.get('id') in ['appendix-16', 'appendix-17', 'appendix-18']:
            items.append({
                'id': app['id'],
                'title': app['title'],
                'kind': 'appendix',
                'printedPage': app.get('printedPage')
            })
            
    # 2. Forms
    for form in toc.get('forms', []):
        items.append({
            'id': form['title'],
            'title': form['title'],
            'kind': 'form',
            'printedPage': form.get('printedPage')
        })
        
    # 3. Special Forms
    for sf in toc.get('specialForms', []):
        items.append({
            'id': sf['title'],
            'title': sf['title'],
            'kind': 'special-form',
            'printedPage': sf.get('printedPage')
        })

    pages_path = os.path.join(base_dir, 'data', 'pages.json')
    with open(pages_path, 'r', encoding='utf-8') as f:
        pages = json.load(f)
        
    pdf_by_printed = {}
    last_printed = 0
    for p in pages:
        if p.get('printedPage'):
            last_printed = int(p['printedPage'])
            pdf_by_printed[last_printed] = p['pdfPage']
        else:
            last_printed += 1
            pdf_by_printed[last_printed] = p['pdfPage']

    # Get their true PDF start pages
    rendering_rules = rendering.get('rules', [])
    for item in items:
        key = item['id']
        
        # Default start page derived from TOC's printedPage
        if 'printedPage' in item and item['printedPage']:
            item['startPdfPage'] = pdf_by_printed.get(int(item['printedPage']))
        
        # Override with page-rendering.json if exists
        for rule in rendering_rules:
            if rule.get('id') == key or rule.get('label') == key:
                if 'pdfPageStart' in rule:
                    item['startPdfPage'] = rule['pdfPageStart']
                elif 'printedPageStart' in rule:
                    item['startPdfPage'] = pdf_by_printed.get(int(rule['printedPageStart']))
                break
                
        if 'startPdfPage' not in item or not item['startPdfPage']:
            raise ValueError(f"Item {key} has no resolved startPdfPage")

    boundaries = []
    for i in range(len(items) - 1):
        prev_item = items[i]
        curr_item = items[i+1]
        
        if prev_item['kind'] == 'appendix' and curr_item['kind'] == 'appendix':
            kind = 'appendix'
        elif prev_item['kind'] == 'form' and curr_item['kind'] == 'form':
            kind = 'form'
        elif prev_item['kind'] == 'special-form' and curr_item['kind'] == 'special-form':
            kind = 'special-form'
        else:
            kind = 'group-transition'
            
        boundaries.append({
            'kind': kind,
            'previous': prev_item['id'],
            'current': curr_item['id'],
            'previousStartPdfPage': prev_item['startPdfPage'],
            'currentStartPdfPage': curr_item['startPdfPage']
        })
        
    if len(boundaries) != 46:
        raise ValueError(f"Expected 46 boundaries, got {len(boundaries)}")
        
    return boundaries

if __name__ == '__main__':
    boundaries = get_authoritative_boundaries()
    print(f"Generated {len(boundaries)} authoritative boundaries.")
    for b in boundaries:
        print(f"{b['kind']}: {b['previous']} (Start: {b['previousStartPdfPage']}) -> {b['current']} (Start: {b['currentStartPdfPage']})")
