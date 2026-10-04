"""Các kiến trúc GNN.

Mỗi module cung cấp ``build_encoder(config)``. ``CWEClassifier`` là head dùng
chung cho trainer:

    graph batch -> GNN encoder -> graph pooling -> classifier -> CWE logits

Không triển khai network giữ chỗ có vẻ như train được. Graph schema và tập
class vẫn là các quyết định còn mở.
"""
