from typing import List
from typing import Union

import torch
from aste.utils import config
from torch import Tensor
from transformers import DebertaModel, AutoModel

from .base_embeddings import BaseEmbedding
from ..span_aggregators import RnnAggregator, BaseAggregator
from ....dataset.reader import Batch


class Transformer(BaseEmbedding):
    def __init__(self, model_name: str = 'Transformer embedding model'):
        dim: int = config['encoder']['transformer']['embedding-dimension']
        super(Transformer, self).__init__(embedding_dim=dim, model_name=model_name)
        self.model: Union[DebertaModel, AutoModel] = self.get_transformer_encoder_from_config()

    def forward(self, batch: Batch, *args, **kwargs) -> Tensor:
        return self.model.forward(batch.sentence, batch.mask).last_hidden_state


class TransformerWithAggregation(BaseEmbedding):
    def __init__(self, model_name: str = 'Transformer with embedding aggregation model'):
        dim: int = config['encoder']['transformer']['embedding-dimension']
        super(TransformerWithAggregation, self).__init__(embedding_dim=dim, model_name=model_name)
        self.model: Union[DebertaModel, AutoModel] = self.get_transformer_encoder_from_config()
        self.aggregator: BaseAggregator = RnnAggregator(input_dim=dim, model_name='RNN Transformer Aggregator',
                                                        num_layers=2)

    def forward(self, batch: Batch, *args, **kwargs) -> Tensor:
        emb: Tensor = self.model.forward(batch.sentence, batch.mask).last_hidden_state
        spans: List[Tensor] = self.construct_spans_ranges(batch)
        return self.aggregator.aggregate(emb, spans)

    @staticmethod
    def construct_spans_ranges(batch: Batch) -> List[Tensor]:
        result_spans: List[Tensor] = list()
        sample: Batch
        for sample in batch:
            words_mask: List[int] = sample.sentence_obj[0].get_sub_words_mask(force_true_mask=True)
            spans: Tensor = torch.tensor(words_mask, device=config['general']['device']).bool()
            spans = spans.nonzero().squeeze()
            spans = torch.nn.functional.pad(spans, [1, 0], mode='constant', value=0)
            spans = torch.nn.functional.pad(spans, [0, 1], mode='constant',
                                            value=sample.sentence_obj[0].encoded_sentence_length - 1)
            spans = torch.nn.functional.pad(spans, [0, 1], mode='constant',
                                            value=sample.sentence_obj[0].encoded_sentence_length)
            unfolded_spans: Tensor = spans.unfold(0, 2, 1).clone()
            unfolded_spans[:, 1] -= 1
            result_spans.append(unfolded_spans)

        return result_spans
