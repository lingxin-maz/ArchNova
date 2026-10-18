# softmax_attention

softmax(Q K^T / sqrt(d_k)) V

Q,K,V have shape [B,N,D]; projection costs excluded; stores dense attention matrix. No causal/position mask specified.

Proposed reference material only. Add source-backed parameter/evidence records before relying on it.
