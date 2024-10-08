from torch.utils.data import Dataset
from transformers.models.seamless_m4t.feature_extraction_seamless_m4t import SeamlessM4TFeatureExtractor
from transformers.models.encodec.feature_extraction_encodec import EncodecFeatureExtractor

import torch
from dataclasses import dataclass
from typing import Dict, List, Union, Any

import pandas as pd
import torchaudio

class CustomDataset(Dataset):
    def __init__(
        self,
        anot: pd.DataFrame,
        wavs_path: str
    ):
        super().__init__()
        self.anot = anot
        self.wavs_path = wavs_path

    def __len__(self):
        return len(self.anot)

    def __getitem__(self, idx):

        sample = self.anot.iloc[idx]

        label = torch.tensor(int(sample.emotion[-1]))

        fn = sample.file.replace("/path_to_wavs/", self.wavs_path)
        waveform, sampling_rate = torchaudio.load(fn)

        waveform_16k = torchaudio.functional.resample(waveform, orig_freq=sampling_rate, new_freq=16000)

        waveform_24k = torchaudio.functional.resample(waveform, orig_freq=sampling_rate, new_freq=24000)

        # print(f"Loaded data for idx {idx}: waveform_16k size {waveform_16k.size()}, waveform_24k size {waveform_24k.size()}")

        return {
            "input_features": waveform_16k, # torch.Tensor
            "input_values": waveform_24k, # torch.Tensor
            "label": label # torch.Tensor
        }


@dataclass
class DataCollatorForSER:
    codec_processor: EncodecFeatureExtractor = EncodecFeatureExtractor.from_pretrained("facebook/encodec_24khz")
    semantic_processor: SeamlessM4TFeatureExtractor = SeamlessM4TFeatureExtractor.from_pretrained("facebook/w2v-bert-2.0")

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        batch = {}

        # for feature in features:
        #     print(feature)
        #     print(feature.keys())

        # Handle input_features (semantic)
        waveforms_16k = [feature["input_features"].numpy()[0] for feature in features]
        semantic_inputs = self.semantic_processor(waveforms_16k, sampling_rate=16000, return_tensors="pt")
        batch.update(**semantic_inputs)

        # Handle input_values (acoustic/codec)
        waveforms_24k = [feature["input_values"].numpy()[0] for feature in features]
        codec_inputs = self.codec_processor(waveforms_24k, sampling_rate=24000, return_tensors="pt")
        batch.update(**codec_inputs)

        # Handle labels
        if "label" in features[0].keys():
            batch["labels"] = torch.tensor([f["label"] for f in features], dtype=torch.long)

        return batch
    