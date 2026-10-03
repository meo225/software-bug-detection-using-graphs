"""GNN architectures.

Each module exposes ``build_encoder(config)``. ``CWEClassifier`` is the shared
head used by the trainer:

    graph batch -> GNN encoder -> graph pooling -> classifier -> CWE logits

Do not implement a placeholder network that looks trainable. The graph schema
and the class set are still open.
"""
