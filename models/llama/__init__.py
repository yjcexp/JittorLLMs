import time
import json
from pathlib import Path
import os
import platform

import jittor as jt
jt.flags.use_cuda = 1
jt.flags.amp_level = 3

from models import LLMModel
from llama import ModelArgs, Transformer, Tokenizer, LLaMA, LLaMA2

os_name = platform.system()
clear_command = 'cls' if os_name == 'Windows' else 'clear'


def load(
    ckpt_dir: str,
    tokenizer_path: str,
    max_seq_len: int,
    max_batch_size: int,
    model_name:str = "llama"
):
    assert model_name in ["llama", "llama2"]
    start_time = time.time()
    checkpoints = sorted(Path(ckpt_dir).glob("*.pth"))
    ckpt_path = str(checkpoints[0])
    print("Loading")
    with jt.flag_scope(use_cuda=0):
        checkpoint = jt.load(ckpt_path)
    with open(Path(ckpt_dir) / "params.json", "r") as f:
        params = json.loads(f.read())
    
    model_args: ModelArgs = ModelArgs(
        max_seq_len=max_seq_len, max_batch_size=max_batch_size, **params
    )
    tokenizer = Tokenizer(model_path=tokenizer_path)
    model_args.vocab_size = tokenizer.n_words
    model = Transformer(model_args)
    model.load_state_dict(checkpoint)
    model.half()
    model.eval()
    
    if model_name == "llama":
        generator = LLaMA(model, tokenizer)
    else:
        generator = LLaMA2(model, tokenizer)
    print(f"Loaded in {time.time() - start_time:.2f} seconds")
    return generator


class LLaMAModel(LLMModel):
    def __init__(self, args) -> None:
        super().__init__()

        ckpt_dir = getattr(args, "ckpt_dir", "data/llama/7BJ")
        tokenizer_path = getattr(args, "tokenizer_path", "data/llama/tokenizer.model")

        self.generator = load(
            ckpt_dir, tokenizer_path, max_seq_len=512, max_batch_size=32,model_name=args.model
        )
        jt.gc()

    def run(self, input_text: str) -> str:
        with jt.no_grad():
            output = self.generator.generate([input_text], max_gen_len=256, temperature=0.8, top_p=0.95)
        text_out = ""
        for output_text in output:
            text_out = output_text
        return text_out

    def chat(self):
        history = ""
        while True:
            session = "用户输入: "
            input_text = input("用户输入: ")
            session += input_text + "\n"
            session += "LLaMA   : "
            with jt.no_grad():
                for output_text in self.generator.generate([input_text], max_gen_len=256, temperature=0.8, top_p=0.95):
                    print(history + session + output_text, flush=True)
                    history += session + output_text + "\n"
    
    def run_web_demo(self, input_text, history=[]):
        response = self.run(input_text)
        history.append([input_text, response])
        yield response, history

class LLaMA2Model(LLMModel):
    def __init__(self, args) -> None:
        super().__init__()

        ckpt_dir = getattr(args, "ckpt_dir", "data/llama/7BJ")
        tokenizer_path = getattr(args, "tokenizer_path", "data/llama/tokenizer.model")

        self.generator = load(
            ckpt_dir, tokenizer_path, max_seq_len=512, max_batch_size=32,model_name=args.model
        )
        jt.gc()

    def chat(self):
        dialog = []
        while True:
            input_text = input("用户输入: ")
            dialog.append({
                "role": "user",
                "content": input_text
            })
            with jt.no_grad():
                results = self.generator.chat_completion([dialog], max_gen_len=128, temperature=0.6, top_p=0.9)
                result = results[0]['generation']
                dialog.append(result)
                print("Assistent:",result['content'], flush=True)
    
    def run_web_demo(self, input_text, history=[]):
        dialog = []
        for prompt, answer in history:
            dialog.append({
                "role": "user",
                "content": prompt
            })
            dialog.append({
                "role": "assistant",
                "content": answer
            })
            
        dialog.append({
                "role": "user",
                "content": input_text
            })
        with jt.no_grad():
            results = self.generator.chat_completion([dialog], max_gen_len=128, temperature=0.6, top_p=0.9)
        result = results[0]['generation']
        response = result['content']
        history.append([input_text, response])
        yield response, history
        
def get_model(args):
    args.ckpt_dir = os.path.join(jt.compiler.ck_path, args.model)
    args.tokenizer_path = os.path.join(jt.compiler.ck_path, args.model, "tokenizer.model")
    if args.model == "llama2":
        return LLaMA2Model(args)
    return LLaMAModel(args)
