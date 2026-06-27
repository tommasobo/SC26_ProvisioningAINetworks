# Fig. 3/4 Composite Mode Sweep

Mode sweep over historical compatibility switches for the microbenchmark Composite-LP metadata path. Lower max relative error is better.

## fig03_auto

| label | max rel diff % | mean rel diff % | max abs diff ns | args |
| --- | ---: | ---: | ---: | --- |
| fig03_auto_rank6_legacy | 18.340441 | 8.438167 | 1405781 | `--program-rank 6 --node-map-mode rank-block --ring-duplicate-policy last --nic-per-rank --force-sequential` |
| fig03_auto_rank4_legacy | 18.389828 | 8.467491 | 1413928 | `--program-rank 4 --node-map-mode rank-block --ring-duplicate-policy last --nic-per-rank --force-sequential` |
| fig03_auto_rank4_default | 34.587062 | 9.985618 | 1512699 | `--program-rank 4` |
| fig03_auto_rank6_default | 37.004869 | 10.752772 | 1620807 | `--program-rank 6` |

## fig03_ch1

| label | max rel diff % | mean rel diff % | max abs diff ns | args |
| --- | ---: | ---: | ---: | --- |
| fig03_ch1_legacy_no_intra | 11.438023 | 5.005515 | 1417439 | `--node-map-mode rank-block --ring-duplicate-policy last --disable-intra-node-transfer` |
| fig03_ch1_default | 11.633719 | 5.086184 | 1441690 | `` |
| fig03_ch1_rank_block_last | 11.713922 | 5.119201 | 1451629 | `--node-map-mode rank-block --ring-duplicate-policy last` |
| fig03_ch1_rank_block | 11.781560 | 5.146966 | 1460011 | `--node-map-mode rank-block` |
| fig03_ch1_rank_block_last_nic_seq | 11.862376 | 5.180329 | 1470026 | `--node-map-mode rank-block --ring-duplicate-policy last --nic-per-rank --force-sequential` |

## fig04_mixed

| label | max rel diff % | mean rel diff % | max abs diff ns | args |
| --- | ---: | ---: | ---: | --- |
| fig04_mixed_rank_block_last_nic_seq | 4.974985 | 4.092718 | 17719766 | `--node-map-mode rank-block --ring-duplicate-policy last --nic-per-rank --force-sequential` |
| fig04_mixed_rank_block_last | 5.006357 | 4.076224 | 17719256 | `--node-map-mode rank-block --ring-duplicate-policy last` |
| fig04_mixed_default | 5.024776 | 4.132172 | 17804341 | `` |
| fig04_mixed_legacy_no_intra | 5.038195 | 4.137883 | 17923386 | `--node-map-mode rank-block --ring-duplicate-policy last --disable-intra-node-transfer` |
| fig04_mixed_rank_block | 5.131941 | 4.237963 | 18583013 | `--node-map-mode rank-block` |

## Conclusion

The tested compatibility switches did not recover bit-exact packaged Fig. 3/4 microbenchmark curves. Fig. 3 1-channel remains around 11.44% max relative error at best; Fig. 3 auto improves to about 18.34% with legacy rank settings but remains far from exact; Fig. 4 mixed remains around 4.97% at best. This supports the report conclusion that these packaged microbenchmark CSVs likely used additional historical assumptions or incomplete metadata, not just the exposed wrapper switches.
