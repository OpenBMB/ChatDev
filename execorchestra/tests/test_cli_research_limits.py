import sys
import pytest
from sgar_mvp.main import parse_args


def test_default_launch_keeps_limits_optional(monkeypatch):
    monkeypatch.setattr(sys,'argv',['framework'])
    args=parse_args()
    assert args.max_generation_requests is None and args.deadline_sec is None


def test_explicit_limits_reach_parsed_configuration(monkeypatch):
    monkeypatch.setattr(sys,'argv',['framework','--max-generation-requests','48','--deadline-sec','1800'])
    args=parse_args()
    assert args.max_generation_requests==48 and args.deadline_sec==1800


@pytest.mark.parametrize('flag,value',[('--max-generation-requests','0'),('--deadline-sec','-1')])
def test_invalid_limits_stop_before_execution(monkeypatch,flag,value):
    monkeypatch.setattr(sys,'argv',['framework',flag,value])
    with pytest.raises(SystemExit) as error:parse_args()
    assert error.value.code==2
