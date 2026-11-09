"""Offline MeloTTS subprocess boundary; no install, download, or external inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import wave
from autonomous_company import Store, require, exact, parse
from goal_dialogue import safe_text
from local_artifacts import run_command


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


class MeloLocal:
    def __init__(self, root='data/tts_korean_review'):
        self.root = Path(root).resolve()

    def synthesize(self, texts, folder):
        folder = Path(folder).resolve()
        require(folder.is_dir() and not any(folder.iterdir()), 'tts_output_not_empty')
        require(isinstance(texts, list) and 1 <= len(texts) <= 24, 'invalid_utterances')
        for value in texts: safe_text(value, 600)
        python = self.root/'runtime-melotts-py310/bin/python'
        require(python.is_file() and python.resolve().is_relative_to(self.root/'runtime-melotts-py310'), 'melo_runtime_missing')
        require((self.root/'models/myshell-ai--MeloTTS-Korean/checkpoint.pth').is_file(), 'melo_model_missing')
        inventory = json.loads((self.root/'model_download_receipt.json').read_text())
        for item in inventory:
            path = self.root/'models'/item['repo'].replace('/', '--')/Path(item['file']).name
            require(file_hash(path) == item['sha256'], 'local_model_changed')
        request = dict(root=str(self.root), texts=texts)
        Store.atomic(folder/'request.json', request)
        # The worker strips credentials and blocks network before importing model libraries.
        run_command([str(python), '-B', str(Path(__file__).resolve()), '--worker', str(folder/'request.json')],
                    stage='local_tts', timeout=600)
        receipt = parse((folder/'receipt.json').read_text())
        require(receipt['engine'] == 'MeloTTS' and len(receipt['utterances']) == len(texts), 'invalid_tts_receipt')
        for item in receipt['utterances']:
            require(file_hash(folder/item['file']) == item['sha256'], 'tts_audio_changed')
        return receipt


def worker(request_path):
    from unittest.mock import patch
    request_path = Path(request_path).resolve()
    request = parse(request_path.read_text()); exact(request, ('root', 'texts'))
    root = Path(request['root']).resolve(); folder = request_path.parent
    require(isinstance(request['texts'], list) and 1 <= len(request['texts']) <= 24, 'invalid_utterances')
    for value in request['texts']: safe_text(value, 600)
    for key in list(os.environ):
        if key.endswith(('_KEY', '_TOKEN', '_SECRET')): os.environ.pop(key, None)
    cache = folder/'cache'; cache.mkdir()
    os.environ.update(HF_HOME=str(cache/'hf'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_IMPLICIT_TOKEN='1', HF_HUB_DISABLE_TELEMETRY='1',
                      NLTK_DATA=str(root/'cache/nltk'), XDG_CACHE_HOME=str(cache),
                      MPLCONFIGDIR=str(cache/'matplotlib'), NUMBA_CACHE_DIR=str(cache/'numba'),
                      OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', AWS_EC2_METADATA_DISABLED='true')
    with patch('socket.socket.connect', side_effect=RuntimeError('offline_tts_network_blocked')), \
         patch('socket.getaddrinfo', side_effect=RuntimeError('offline_tts_dns_blocked')):
        import torch
        import numpy as np
        import soundfile as sf
        from transformers import AutoTokenizer, AutoModelForMaskedLM
        import unidic, unidic_lite
        unidic.DICDIR = unidic_lite.DICDIR
        torch.set_num_threads(2); torch.set_num_interop_threads(1); torch.manual_seed(42); np.random.seed(42)
        aliases = {'bert-base-uncased':'google-bert/bert-base-uncased',
                   'bert-base-multilingual-uncased':'google-bert/bert-base-multilingual-uncased'}
        inventory = json.loads((root/'model_inventory.json').read_text())
        allowed = {x['repo'] for x in inventory}
        def local_path(name):
            name = aliases.get(str(name), str(name))
            require(name in allowed, 'unapproved_model')
            path = root/'models'/name.replace('/', '--')
            require(path.is_dir(), 'local_model_missing')
            return str(path)
        original_tokenizer = AutoTokenizer.from_pretrained
        original_model = AutoModelForMaskedLM.from_pretrained
        def tokenizer(name, *args, **kwargs):
            kwargs['local_files_only'] = True
            return original_tokenizer(local_path(name), *args, **kwargs)
        def model_loader(name, *args, **kwargs):
            kwargs['local_files_only'] = True
            return original_model(local_path(name), *args, **kwargs)
        AutoTokenizer.from_pretrained = staticmethod(tokenizer)
        AutoModelForMaskedLM.from_pretrained = staticmethod(model_loader)
        from melo.api import TTS
        model_path = root/'models/myshell-ai--MeloTTS-Korean'
        model = TTS(language='KR', device='cpu', config_path=str(model_path/'config.json'), ckpt_path=str(model_path/'checkpoint.pth'))
        utterances = []
        for index, text in enumerate(request['texts']):
            spoken = text.replace('ChatGPT', '챗지피티')
            output = folder/f'voice-{index:02}.wav'
            require(not output.exists(), 'tts_audio_exists')
            model.tts_to_file(spoken, model.hps.data.spk2id['KR'], str(output), speed=1.0, quiet=True)
            audio, sr = sf.read(output)
            require(audio.ndim == 1 and sr == 44100 and np.isfinite(audio).all(), 'invalid_tts_audio')
            require(float(np.sqrt(np.mean(audio**2))) > .001 and float(np.mean(np.abs(audio) >= .999)) < .001, 'silent_or_clipped_tts')
            utterances.append(dict(file=output.name, text=text, spoken_text=spoken, duration=len(audio)/sr,
                                   sample_rate=sr, sha256=file_hash(output)))
        Store.atomic(folder/'receipt.json', dict(engine='MeloTTS', device='cpu', speed=1.0,
            model='myshell-ai/MeloTTS-Korean', model_sha256=file_hash(model_path/'checkpoint.pth'),
            utterances=utterances, network=False, external_api_calls=0, human_listening_verified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--worker', required=True)
    worker(parser.parse_args().worker)
