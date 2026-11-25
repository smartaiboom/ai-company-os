"""Explicit Windows local Korean voice selection for WSL review previews."""
import base64
from binascii import Error
import json
import os
from pathlib import Path
import subprocess
import wave

from autonomous_company import CompanyError, Store, require
from goal_dialogue import safe_text
from local_artifacts import run_command
from local_melo_tts import file_hash

ENGINE = 'Windows Heami (local)'
POWERSHELL = Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
VOICE_FILE = Path('/mnt/c/Windows/Speech_OneCore/Engines/TTS/ko-KR/M1042Heami.APM')
SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object {
    $_.Language -eq 'ko-KR' -and $_.DisplayName -eq 'Microsoft Heami'
} | Select-Object -First 1
if (-not $voice -or -not $asTask) { throw 'local_voice_unavailable' }
$inputJson = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd()))
$items = ConvertFrom-Json $inputJson
$synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
try {
    $synth.Voice = $voice
    foreach ($line in $items.texts) {
        $operation = $synth.SynthesizeTextToStreamAsync($line)
        $task = $asTask.MakeGenericMethod($streamType).Invoke($null,@($operation))
        $task.Wait()
        $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($task.Result)
        $buffer = [IO.MemoryStream]::new()
        try {
            $stream.CopyTo($buffer)
            [Console]::WriteLine([Convert]::ToBase64String($buffer.ToArray()))
        } finally {
            $buffer.Dispose()
            $stream.Dispose()
        }
    }
} finally {
    $synth.Dispose()
}
"""


class HeamiLocal:
    def available(self):
        return bool(os.getenv('WSL_INTEROP') and POWERSHELL.is_file() and VOICE_FILE.is_file())

    def synthesize(self, texts, folder):
        require(self.available(), 'heami_local_voice_missing')
        require(folder.is_dir() and not any(folder.iterdir()) and 1<=len(texts)<=12,'invalid_utterances')
        for line in texts:
            safe_text(line,300)
        script = base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')
        payload = base64.b64encode(json.dumps({'texts':texts},ensure_ascii=False).encode())
        env = {key:value for key,value in os.environ.items()
               if not key.endswith(('_KEY','_TOKEN','_SECRET')) and key!='WSLENV'}
        try:
            process = subprocess.run([str(POWERSHELL),'-NoProfile','-NonInteractive','-EncodedCommand',script],
                                     input=payload,capture_output=True,timeout=90,env=env)
            lines = process.stdout.splitlines()
            require(process.returncode==0 and len(lines)==len(texts),'heami_local_synthesis_failed')
            require(all(len(line)<=8*1024*1024 for line in lines),'heami_voice_too_large')
            samples = [base64.b64decode(line,validate=True) for line in lines]
        except (OSError,subprocess.TimeoutExpired,Error) as exc:
            raise CompanyError('heami_local_synthesis_failed') from exc
        utterances = []
        for i,(line,sample) in enumerate(zip(texts,samples,strict=True)):
            require(sample[:4]==b'RIFF' and sample[8:12]==b'WAVE','invalid_speech_format')
            original = folder/f'heami-original-{i:02}.wav'
            original.write_bytes(sample)
            output = folder/f'voice-{i:02}.wav'
            run_command(['ffmpeg','-nostdin','-v','error','-i',str(original),'-ac','1','-ar','44100',
                         '-c:a','pcm_s16le',str(output)],stage='local_tts')
            with wave.open(str(output),'rb') as wav:
                duration=wav.getnframes()/44100
            utterances.append(dict(file=output.name,text=line,spoken_text=line,duration=duration,sha256=file_hash(output)))
        receipt=dict(engine=ENGINE,utterances=utterances,network=False,external_api_calls=0,
                     voice_use='local_review_only',human_listening_verified=False)
        Store.atomic(folder/'receipt.json',receipt)
        return receipt
