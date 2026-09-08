"""Explainable comparisons with public Medicare locality benchmarks.

This is descriptive analysis of administrative rates, not a market-price model,
coverage decision, overcharge determination, or estimate of recoverable savings.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
import json
from pathlib import Path

from medbill.reference import DEFAULT_DB, connect, lookup

MIN_COHORT = 20
PERCENTILE = Decimal('0.95')


def dollars(cents):
    return format((Decimal(cents)/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')


def distribution(values, unit_charge_cents):
    """Nearest-rank p95 and midrank empirical percentile; no normality assumption.

    Minimum n=20 and strict >p95 are explicit product rules, not significance
    tests. One observation per carrier/locality; equal rates remain distinct.
    """
    values=sorted(Decimal(v) for v in values)
    result={'n':len(values),'minimum_n':MIN_COHORT,'p95_method':'nearest_rank',
            'flag':None,'percentile_rank':None,'p95_usd':None}
    if len(values)<MIN_COHORT:
        return result | {'availability':'insufficient_cohort'}
    if len(set(values))==1:
        return result | {'availability':'no_geographic_variation'}
    charge=Decimal(unit_charge_cents)
    rank=int((PERCENTILE*len(values)).to_integral_value(rounding=ROUND_CEILING))
    p95=values[rank-1]
    lower=sum(v<charge for v in values)
    equal=sum(v==charge for v in values)
    percentile=100*(Decimal(lower)+Decimal(equal)/2)/len(values)
    return result | {'availability':'available','p95_usd':dollars(p95),
        'min_usd':dollars(values[0]),'max_usd':dollars(values[-1]),
        'percentile_rank':format(percentile.quantize(Decimal('.01')),'f'),
        'flag':charge>p95,'flag_rule':'unit charge strictly greater than nearest-rank p95',
        'meaning':'Percentile among Medicare locality rates, not commercial charges or error probability.'}


class Comparator:
    def __init__(self, *, carrier, locality, setting, category, db_path=DEFAULT_DB):
        self.context=dict(carrier=carrier,locality=locality,setting=setting,category=category)
        self.db_path=db_path
        self._cohorts={}

    def cohort(self,code,modifier,date):
        key=(code,modifier,date)
        if key in self._cohorts:
            return self._cohorts[key]
        with connect(self.db_path) as db:
            pairs=db.execute('''SELECT carrier,locality FROM payment_rates
                WHERE code=? AND modifier=? AND category=? ORDER BY carrier,locality''',
                (code,modifier,self.context['category'])).fetchall()
        members=[]
        exclusions=Counter()
        sources={}
        for pair in pairs:
            context=self.context | dict(pair)
            ref=lookup(code,modifier=modifier,service_date=date,db_path=self.db_path,**context)
            if ref['availability']!='published_benchmark' or ref.get('status')!='A':
                exclusions[ref['availability'] if ref['availability']!='published_benchmark' else 'conditional_payment']+=1
                continue
            cents=int(Decimal(ref['benchmark_usd'])*100)
            sources[ref['source']['id']]=ref['source']
            members.append(dict(pair) | {'benchmark_cents':cents,'source_id':ref['source']['id'],
                                         'source_row':ref['source_row']})
        result={'members':members,'excluded':dict(exclusions),'sources':sources,
                'definition':{'code':code,'modifier':modifier,'service_date':date,
                              'setting':self.context['setting'],'category':self.context['category'],
                              'status':'A','weighting':'one equal-weight observation per carrier/locality'}}
        self._cohorts[key]=result
        return result

    def compare_item(self,item):
        result={'code':item.get('code'),'modifier':item.get('modifier'),
                'service_date':item.get('service_date'),'description':item.get('description'),
                'quantity':item.get('quantity'),'charged_cents':item.get('charged_cents'),
                'page':item.get('page'),'line_index':item.get('line_index'),
                'flag':None,'amount_above_benchmark_usd':None}
        if item.get('status')!='parsed' or item.get('issues'):
            return result | {'availability':'ocr_review_required','issues':item.get('issues',[])}
        try:
            quantity=Decimal(str(item.get('quantity')))
            charged=item.get('charged_cents')
            if not quantity.is_finite() or quantity<=0 or type(charged) is not int or charged<0:
                raise ValueError('Invalid quantity or charge')
            if not all(isinstance(item.get(k),str) for k in ('code','modifier','service_date')):
                raise ValueError('Missing matching fields')
            ref=lookup(item['code'],modifier=item['modifier'],service_date=item['service_date'],
                       db_path=self.db_path,**self.context)
        except (ValueError,InvalidOperation):
            return result | {'availability':'invalid_input'}
        result['reference']=ref
        if ref['availability']!='published_benchmark':
            return result | {'availability':ref['availability']}
        if ref['status']!='A':
            return result | {'availability':'conditional_payment_requires_review'}
        benchmark=Decimal(ref['benchmark_usd'])*100
        line_benchmark=(quantity*benchmark).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        excess=max(Decimal(0),Decimal(charged)-line_benchmark)
        unit_charge=Decimal(charged)/quantity
        cohort=self.cohort(item['code'],item['modifier'],item['service_date'])
        stats=distribution([m['benchmark_cents'] for m in cohort['members']],unit_charge)
        return result | {'availability':'compared','unit_charge_usd':dollars(unit_charge),
            'unit_benchmark_usd':ref['benchmark_usd'],'line_benchmark_usd':dollars(line_benchmark),
            'charge_to_local_benchmark_ratio':format((Decimal(charged)/line_benchmark).quantize(Decimal('.0001')),'f') if line_benchmark else None,
            'amount_above_benchmark_usd':dollars(excess),
            'flag':(stats['flag'] and unit_charge>benchmark) if stats['flag'] is not None else None,
            'decision_rule':'unit charge exceeds BOTH the matched local rate and geographic p95',
            'statistics':stats,'cohort':cohort,'warnings':ref['warnings']+[
                'Quantity times the full single-service rate; claim-specific reductions are not calculated.',
                'A flag identifies a Medicare benchmark difference to investigate, not an overcharge.']}

    def compare(self,extraction):
        items=[self.compare_item(item) for item in extraction['items']]
        compared=[i for i in items if i['availability']=='compared']
        excess=sum((Decimal(i['amount_above_benchmark_usd']) for i in compared),Decimal(0))
        return {'context':self.context,'items':items,'summary':{
            'candidate_rows':len(items),'compared_rows':len(compared),
            'excluded_rows':len(items)-len(compared),'flagged_rows':sum(i['flag'] is True for i in items),
            'excluded_reasons':dict(Counter(i['availability'] for i in items if i['availability']!='compared')),
            'amount_above_medicare_benchmark_usd':format(excess.quantize(Decimal('.01')),'f') if compared else None,
            'scope':'Sum of positive differences for compared rows only; excluded rows contribute neither zero nor an estimate.',
            'meaning':'Not a confirmed overcharge, patient responsibility, or recoverable savings.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extraction',type=Path)
    parser.add_argument('--synthetic',action='store_true',required=True)
    for field in ['carrier','locality','setting','category']:
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--db-path',type=Path,default=DEFAULT_DB)
    args=vars(parser.parse_args())
    path=args.pop('extraction'); args.pop('synthetic')
    print(json.dumps(Comparator(**args).compare(json.loads(path.read_text(encoding='utf-8'))),indent=2))


if __name__=='__main__': main()
