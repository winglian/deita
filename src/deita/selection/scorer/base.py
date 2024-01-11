from functools import partial

import numpy as np
from scipy.special import softmax
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging

logger = logging.getLogger(__name__)

class Scorer(object):

    def __init__(self, model_name_or_path: str, is_vllm: bool = False, api: str = None):

        self.is_vllm = is_vllm
        self.is_api = bool(api)
        self.model_name_or_path = model_name_or_path

        if is_vllm:
            from vllm import LLM, SamplingParams

            self.llm = LLM(model_name_or_path)
            self.sampling_params = SamplingParams(max_tokens = 512, logprobs = 1000)
        elif self.is_api:
            from openai import OpenAI

            client = OpenAI(base_url=api, api_key="loremipsum")
            self.openai = partial(client.completions.create, model=model_name_or_path)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
            self.model = AutoModelForCausalLM.from_pretrained(model_name_or_path)


    def infer_score(self, user_input: str):

        max_length = 512

        if self.is_vllm:
            outputs = self.llm.generate(user_input, self.sampling_params)
            score_template = np.array([1,2,3,4,5,6])

            try:
                logprobs_list = outputs[0].outputs[0].logprobs[0]
            except IndexError:
                logger.warning("Meeting Index Error. Returning A Placeholder Score -1.")
                return -1
        elif self.is_api:
            res = self.openai(
                prompt=user_input,
                max_tokens=512,
                logprobs=1000,
            )
            logprobs_list = res.choices[0].logprobs.top_logprobs[0]
        else:
            input_ids = self.tokenizer.encode(user_input, return_tensors = "pt")
            outputs = self.model.generate(input_ids, max_length = max_length, num_return_sequences = 1, return_dict_in_generate = True, output_scores = True)
            logprobs_list = outputs.scores[0][0]

        score_logits = []
        score_template = np.array([1,2,3,4,5,6])
        if not self.is_api:
            for k in self.id2score:
                score_logits.append(logprobs_list[k])
        else:
            for k in self.id2score.values():
                score_logits.append(logprobs_list[k])
        score_logits = np.array(score_logits)
        score_npy = softmax(score_logits, axis=0)
        score_npy = score_npy * score_template

        score_npy = np.sum(score_npy, axis=0)

        return score_npy

    def infer_complexity(self, input_text: str):

        complexity_template = self.complexity_template
        user_input = complexity_template.format(instruction=input_text)

        return self.infer_score(user_input)

    def infer_quality(self, input_text: str, resp_text: str):

        quality_template = self.quality_template
        user_input = quality_template.format(instruction=input_text, output=resp_text)

        return self.infer_score(user_input)

    @property
    def id2score(self):
        raise NotImplementedError

    @property
    def complexity_template(self):
        raise NotImplementedError

    @property
    def quality_template(self):
        raise NotImplementedError