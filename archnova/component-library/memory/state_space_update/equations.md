# state_space_update

h[t+1] = A h[t] + B x[t]; y[t] = C h[t+1]

Dense A:[H,H], B:[H,D], C:[D,H]; recurrence is sequential; memory excludes stored outputs, parameters and training activations. B in costs denotes batch size. Stability requires a suitable A; not guaranteed.

Proposed reference material only. Add source-backed parameter/evidence records before relying on it.
