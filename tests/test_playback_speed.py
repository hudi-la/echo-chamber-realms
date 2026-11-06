import io
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from echo.config import parse_config
from echo.mouth import OpenAISynth


def test_speed_changes_duration_and_frequency_together_without_changing_samples():
    rate = 24000
    samples = np.sin(2 * np.pi * 400 * np.arange(rate) / rate).astype('float32') * 0.2
    stream = io.BytesIO()
    sf.write(stream, samples, rate, format='WAV', subtype='FLOAT')
    synth = OpenAISynth(None, 'model', {}, {})
    normal, normal_rate = synth._decode_and_shift(stream.getvalue(), 0)
    fast, fast_rate = synth._decode_and_shift(stream.getvalue(), 0, 1.15)
    np.testing.assert_array_equal(normal, fast)
    assert fast_rate == 27600
    assert len(fast) / fast_rate == pytest.approx(1 / 1.15)
    peak = np.argmax(np.abs(np.fft.rfft(fast)))
    assert peak * fast_rate / len(fast) == pytest.approx(460)


@pytest.mark.parametrize('value', ['0', '-1', 'nan', '3'])
def test_invalid_playback_speed_is_rejected(value):
    with pytest.raises(ValueError, match='playback_speed'):
        parse_config('[mouth]\nplayback_speed = ' + value, Path('/tmp'))


def test_default_and_configured_playback_speed():
    assert parse_config('', Path('/tmp')).mouth_speed == 1.0
    assert parse_config('[mouth]\nplayback_speed=1.15', Path('/tmp')).mouth_speed == 1.15
