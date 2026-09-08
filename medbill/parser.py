"""Conservative line-item extraction from OCR words, not from a bill manifest.

Column positions come from detected headers. Regex fallback accepts only one
monetary amount. Missing/ambiguous fields stay null and retain their raw text.
"""
import datetime as dt
from decimal import Decimal
import re

DATE = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b')
CODE = re.compile(r'(?<![A-Z0-9])([0-9]{5}|[A-Z][0-9]{4}|[0-9]{4}[A-Z])(?:[- ](26|TC|[0-9]{2}))?(?![A-Z0-9])')
MONEY = re.compile(r'(?<![\w.])(?:\$\s*)?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)')
SUMMARY = re.compile(r'^(?:total\b|subtotal\b|balance\b|amount due\b|patient (?:balance|payment|responsibility)\b|insurance\b|adjustments?\b|payments?\b)',re.I)


def money(text):
    matches = list(MONEY.finditer(text))
    if len(matches)!=1 or text[:matches[0].start()].strip(' $') or text[matches[0].end():].strip():
        return None
    return int(Decimal(matches[0].group().replace('$','').replace(',','').strip())*100)


def header_columns(line):
    labels={}
    for word in line.get('words',[]):
        token=re.sub(r'[^a-z/]','',word['text'].lower())
        field = ('code' if token in ('code','cpt','hcpcs','cpt/hcpcs') else
                 'description' if token in ('description','service/description') else
                 'quantity' if token in ('qty','quantity','units') else
                 'unit_price' if token == 'price' else
                 'charge' if token in ('charge','charged','charges','amount') else None)
        if field:
            labels[field]=word['left']
    if {'code','description','quantity','charge'} <= labels.keys():
        return labels
    return None


def column_words(line,columns):
    # Header starts define the next column boundary, with a small font-scaled
    # allowance for right-aligned currency. Supported tables are documented.
    anchors=sorted(columns.items(),key=lambda item:item[1])
    buckets={name:[] for name in columns}
    margin=max(5,round(sum(w['height'] for w in line['words'])/max(1,len(line['words']))*0.5))
    for word in line['words']:
        x=word['left']
        preceding=[name for name,left in anchors if x>=left-margin]
        if preceding:
            buckets[preceding[-1]].append(word)
    return buckets


def parse_lines(lines):
    items, rejected, ignored, columns = [], [], [], None
    current_page=None
    for index,line in enumerate(lines):
        text=line['text'].strip()
        if line.get('page',1)!=current_page:
            current_page=line.get('page',1)
            columns=None
        header=header_columns(line)
        if header:
            columns=header
            ignored.append({'page':current_page,'text':text,'reason':'table_header'})
            continue
        if SUMMARY.match(text):
            ignored.append({'page':current_page,'text':text,'reason':'summary_not_line_item'})
            continue
        date_match=DATE.search(text)
        without_date=DATE.sub('',text).strip()
        code_match=CODE.search(without_date)
        # A row must have a service date plus charge/code evidence, or be a
        # code-led fallback row. This excludes account numbers in page headers.
        candidate=bool(date_match and (MONEY.search(without_date) or code_match)) or bool(CODE.match(text) and MONEY.search(text))
        if not candidate:
            ignored.append({'page':current_page,'text':text,'reason':'not_recognized_as_service_row'})
            continue
        buckets=column_words(line,columns) if columns and line.get('words') else {}
        fields={key:' '.join(w['text'] for w in words) for key,words in buckets.items()}
        field_confidence={key:round(min(w['confidence'] for w in words),2) if words else None
                          for key,words in buckets.items()}
        issues=[]
        raw_code=fields.get('code','')
        if fields:
            found=CODE.fullmatch(raw_code.strip())
        else:
            found=code_match
        code=found.group(1) if found else None
        modifier=found.group(2) or '' if found else None
        if code is None:
            issues.append('missing_or_unrecognized_code')
        date=None
        if date_match:
            raw=date_match.group()
            try:
                date=(dt.datetime.strptime(raw,'%m/%d/%Y').date() if '/' in raw else dt.date.fromisoformat(raw)).isoformat()
            except ValueError:
                issues.append('invalid_service_date')
        else:
            issues.append('missing_service_date')
        quantity=None
        amount=None
        if fields:
            description=fields['description'].strip()
            quantity_text=fields['quantity'].strip()
            if re.fullmatch(r'\d+(?:\.\d+)?',quantity_text) and Decimal(quantity_text)>0:
                quantity=str(Decimal(quantity_text).normalize())
            amount=money(fields['charge'])
        else:
            # Without header geometry, monetary columns and trailing numbers
            # cannot be certified as a particular bill field. Keep the candidate
            # extraction, but require review before downstream comparisons.
            issues.append('unverified_layout_without_headers')
            amounts=list(MONEY.finditer(without_date))
            description=without_date
            if found:
                description=description[:found.start()]+description[found.end():]
            if len(amounts)==1:
                match=amounts[0]
                amount=money(match.group())
                before=without_date[:match.start()].rstrip()
                qty=re.search(r'\b(\d+(?:\.\d+)?)\s*$',before)
                if qty and (not found or qty.start()>=found.end()) and Decimal(qty.group(1))>0:
                    quantity=str(Decimal(qty.group(1)).normalize())
                    description=CODE.sub('',before[:qty.start()]).strip()
                else:
                    description=CODE.sub('',before).strip()
            else:
                issues.append('ambiguous_amount_columns')
        if quantity is None:
            issues.append('missing_or_ambiguous_quantity')
        if amount is None:
            issues.append('missing_or_ambiguous_charge')
        if not description:
            issues.append('missing_description')
        if re.search(r'(?:-\s*\$?|\(\s*\$?)\s*\d[\d,]*\.\d{2}',fields.get('charge',without_date)):
            amount=None
            issues.append('negative_or_credit_amount_requires_review')
        # 80 is an explicit conservative review heuristic, not a calibrated
        # accuracy probability. Never repair uncertain digits with reference data.
        if field_confidence.get('code') is not None and field_confidence['code']<80:
            code,modifier=None,None
            issues.append('low_confidence_code')
        if field_confidence.get('quantity') is not None and field_confidence['quantity']<80:
            quantity=None
            issues.append('low_confidence_quantity')
        if field_confidence.get('charge') is not None and field_confidence['charge']<80:
            amount=None
            issues.append('low_confidence_charge')
        date_words=[w for w in line.get('words',[]) if DATE.search(w['text'])]
        if date_words and min(w['confidence'] for w in date_words)<80:
            date=None
            issues.append('low_confidence_service_date')
        confidence=line.get('confidence')
        if confidence is not None and confidence<60:
            issues.append('low_ocr_confidence')
        item={'page':current_page,'line_index':index,'service_date':date,'code':code,
              'modifier':modifier,'description':description,'quantity':quantity,
              'charged_cents':amount,'charged_usd':f'{amount/100:.2f}' if amount is not None else None,
              'ocr_confidence':confidence,'field_confidence':field_confidence,
              'raw_text':text,'raw_columns':fields,
              'issues':issues,'status':'needs_review' if issues else 'parsed'}
        items.append(item)
        if issues:
            rejected.append({'page':current_page,'text':text,'issues':issues})
    return {'items':items,'review_rows':rejected,'ignored_lines':ignored,
            'summary':{'candidate_rows':len(items),'parsed_rows':sum(i['status']=='parsed' for i in items),
                       'review_rows':len(rejected)},
            'warnings':[] if items else ['No service rows recognized; request a clearer itemized sample.']}


def parse_text(text):
    return parse_lines([{'text':line,'page':1} for line in text.splitlines() if line.strip()])
