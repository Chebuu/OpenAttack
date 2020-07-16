from ..attacker import Attacker
from ..utils import detokenizer
import numpy as np


DEFAULT_CONFIG = {
    "unk": "unk",  # unk token
    "scoring": "replaceone",  # replaceone, temporal, tail, combined
    "transformer": "homoglyph",  # homoglyph, swap
    "power": 5
}
homos = {
         '-': '˗', '9': '৭', '8': 'Ȣ', '7': '𝟕', '6': 'б', '5': 'Ƽ', '4': 'Ꮞ', '3': 'Ʒ', '2': 'ᒿ', '1': 'l', '0': 'O',
         "'": '`', 'a': 'ɑ', 'b': 'Ь', 'c': 'ϲ', 'd': 'ԁ', 'e': 'е', 'f': '𝚏', 'g': 'ɡ', 'h': 'հ', 'i': 'і', 'j': 'ϳ',
         'k': '𝒌', 'l': 'ⅼ', 'm': 'ｍ', 'n': 'ո', 'o': 'о', 'p': 'р', 'q': 'ԛ', 'r': 'ⲅ', 's': 'ѕ', 't': '𝚝', 'u': 'ս',
         'v': 'ѵ', 'w': 'ԝ', 'x': '×', 'y': 'у', 'z': 'ᴢ'
}


class DeepWordBugAttacker(Attacker):
    def __init__(self, **kwargs):
        """
        :param string unk: Unknown token used in Classifier. **Default:** 'unk'
        :param string scoring: Scoring function used to compute word importance. **Default:** :any:`replaceone`
        :param string transformer: Transform function to modify a word. **Default:** :any:`homoglyph`

        :Package Requirements:
            * torch
        :Classifier Capacity: Probability

        Black-box Generation of Adversarial Text Sequences to Evade Deep Learning Classifiers. Ji Gao, Jack Lanchantin, Mary Lou Soffa, Yanjun Qi. IEEE SPW 2018.
        `[pdf] <https://ieeexplore.ieee.org/document/8424632>`__
        `[code] <https://github.com/QData/deepWordBug>`__
        """
        self.config = DEFAULT_CONFIG.copy()
        self.config.update(kwargs)
        self.scoring = self.config["scoring"]
        self.transformer = self.config["transformer"]
        self.power = self.config["power"]

    def __call__(self, clsf, x_orig, target=None):
        import torch
        """
        * **clsf** : **Classifier** .
        * **x_orig** : Input sentence.
        """
        y_orig = clsf.get_pred([x_orig])[0]
        inputs = x_orig.strip().lower().split(" ")
        losses = self.scorefunc(self.scoring, clsf, inputs, y_orig)  # 每个词消失后的loss向量
        sorted, indices = torch.sort(losses, descending=True)

        advinputs = inputs[:]
        t = 0
        j = 0
        while j < self.power and t < len(inputs):
            if advinputs[indices[t]] != '' and advinputs[indices[t]] != ' ':
                advinputs[indices[t]] = self.transform(self.transformer, advinputs[indices[t]])
                j += 1
            t += 1

        output2 = clsf.get_pred([detokenizer(advinputs)])[0]
        if target is None:
            if output2 != y_orig:
                return detokenizer(advinputs), output2
        else:
            if int(output2) is int(target):
                return detokenizer(advinputs), output2
        return None

    def scorefunc(self, type, clsf, inputs, y_orig):
        if "replaceone" in type:
            return self.replaceone(clsf, inputs, y_orig)
        elif "temporal" in type:
            return self.temporal(clsf, inputs, y_orig)
        elif "tail" in type:
            return self.temporaltail(clsf, inputs, y_orig)
        elif "combined" in type:
            return self.combined(clsf, inputs, y_orig)
        else:
            print("error, No scoring func found")

    def transform(self, type, word):
        if "homoglyph" in type:
            return self.homoglyph(word)
        elif "swap" in type:
            return self.temporal(word)
        else:
            print("error, No transform func found")

    # scoring functions
    def replaceone(self, clsf, inputs, y_orig):
        import torch

        losses = torch.zeros(len(inputs))
        for i in range(len(inputs)):
            tempinputs = inputs[:]  # ##
            tempinputs[i] = self.config['unk']
            with torch.no_grad():
                tempoutput = torch.from_numpy(clsf.get_prob([" ".join(tempinputs)]))  # ##
            softmax = torch.nn.Softmax(dim=1)
            nll_lossed = -1 * torch.log(softmax(tempoutput))[0][y_orig].item()
            # losses[i] = F.nll_loss(tempoutput, torch.tensor([[y_orig]], dtype=torch.long), reduce=False)
            losses[i] = nll_lossed  # ##
            # print(" ".join(tempinputs), nll_lossed)
        return losses

    def temporal(self, clsf, inputs, y_orig):
        import torch
        softmax = torch.nn.Softmax(dim=1)

        losses1 = torch.zeros(len(inputs))
        dloss = torch.zeros(len(inputs))
        for i in range(len(inputs)):
            tempinputs = inputs[: i + 1]
            with torch.no_grad():
                tempoutput = torch.from_numpy(clsf.get_prob([detokenizer(tempinputs)]))
            # losses1[i] = F.nll_loss(tempoutput, y_orig, reduce=False)
            losses1[i] = -1 * torch.log(softmax(tempoutput))[0][y_orig].item()
            print(detokenizer(tempinputs), losses1[i])
        for i in range(1, len(inputs)):
            dloss[i] = abs(losses1[i] - losses1[i - 1])
        return dloss

    def temporaltail(self, clsf, inputs, y_orig):
        import torch
        softmax = torch.nn.Softmax(dim=1)

        losses1 = torch.zeros(len(inputs))
        dloss = torch.zeros(len(inputs))
        for i in range(len(inputs)):
            tempinputs = inputs[i:]
            with torch.no_grad():
                tempoutput = torch.from_numpy(clsf.get_prob([detokenizer(tempinputs)]))
            # losses1[i] = F.nll_loss(tempoutput, y_orig, reduce=False)
            losses1[i] = -1 * torch.log(softmax(tempoutput))[0][y_orig].item()
        for i in range(1, len(inputs)):
            dloss[i] = abs(losses1[i] - losses1[i - 1])
        return dloss

    def combined(self, clsf, inputs, y_orig):
        temp = self.temporal(clsf, inputs, y_orig)
        temptail = self.temporaltail(clsf, inputs, y_orig)
        return (temp+temptail) / 2

    # transform functions
    def homoglyph(self, word):
        s = np.random.randint(0, len(word))
        if word[s] in homos:
            rletter = homos[word[s]]
        else:
            rletter = word[s]
        cword = word[:s] + rletter + word[s+1:]
        return cword

    def swap(self, word):
        if len(word) != 1:
            s = np.random.randint(0, len(word)-1)
            cword = word[:s] + word[s+1] + word[s] + word[s+2:]
        else:
            cword = word
        return cword
