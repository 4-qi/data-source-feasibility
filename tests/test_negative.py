"""Synthetic regression tests; no network requests."""
import json
import pytest
from types import SimpleNamespace
from feasibility.collectors import steam
from feasibility.http import StopCollection
from feasibility.reporting import summarize


class FakeClient:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def get(self,url,params=None):
        self.calls.append(params);return next(self.responses)


def review(rid,flag=False):
    return {'recommendationid':rid,'review':'The synthetic controls did not work for me.',
            'timestamp_created':1,'timestamp_updated':2,'voted_up':flag}


def test_negative_filter_and_false_flags_preserved():
    c=FakeClient([{'reviews':[review(1),review(2)]},{'reviews':[review(3),review(4)]}])
    out=steam.collect_negative(c)
    assert len(c.calls)==2 and len(out.records)==4
    assert all(json.loads(x['input_json'])['review_type']==2 for x in c.calls)
    assert all(r.metadata['voted_up'] is False and r.fields['voted_up'] for r in out.records)


def test_all_reviews_default_remains_zero():
    c=FakeClient([{'reviews':[]}]);steam.page(c,620,1,2)
    assert json.loads(c.calls[0]['input_json'])['review_type']==0


def test_duplicate_negative_ids_are_counted_without_losing_false():
    c=FakeClient([{'reviews':[review(1),review(1)]}])
    out=steam.collect_negative(c,appids=(620,),max_records=2)
    transport=SimpleNamespace(host='api.steampowered.com',events=[],blocked=False)
    s=summarize('steam',{'max_records':2},out,transport,'2026-10-20T00:00:00+00:00')
    assert s['duplicate_records']==1 and s['unique_records_with_id']==1
    assert s['record_metrics'][0]['metadata']['voted_up'] is False


@pytest.mark.parametrize('flag',[True,None,0,'false'])
def test_negative_label_mismatch_stops_before_second_game(flag):
    c=FakeClient([{'reviews':[review(1,flag)]}])
    with pytest.raises(StopCollection,match='negative_filter_label_mismatch'):
        steam.collect_negative(c)
    assert len(c.calls)==1 and len(c.collected.records)==1


def test_empty_negative_sample_does_not_fabricate_records():
    c=FakeClient([{'reviews':[]},{'reviews':[]}])
    assert steam.collect_negative(c).records==[]
