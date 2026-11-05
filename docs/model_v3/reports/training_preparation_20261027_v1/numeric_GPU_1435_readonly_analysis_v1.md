# Numeric GPU1435: readonly result analysis v1

The registered candidate remains FAILED and must not be adopted. Actual job
4521435 completed all48 cases/192 encoder forwards:10PASS,38FAIL,0error,0skip.
RESULT has failure=null (no operational exception), status=FAIL and unchanged
before/after sources. Full collection is distinct from successful physics.
The original38 failed cases and their original measurements remain intact.

This report reads only RESULT.json and the48 closed __numeric_case.json files.
No NPZ body, coordinate/H0/weight array or SDK was read. No Python, model forward,
training, new candidate or new scientific numerical experiment was executed.
Counts/extrema below aggregate already saved JSON. The explicitly labelled
nearest-FP32 distances use only81 saved scalar argmax values; they are metadata
checks, not a new tensor experiment or an all-component impossibility theorem.

## Observed failures

All81 failed field/transform observations (of1872 total) have argmax graph row2,
the32-atom molecule. All48 geometry-domain tests, neighbor identities and nonzero
terminal checks pass. Largest recorded noise pushforward residual is
4.6147705909382886e-7 Angstrom. No evidence here supports a changed hard-cutoff
edge, wrong transformation rule, regenerated noise or zero-output explanation.

|Field|Failed/144|Maximum absolute error|
|---|---:|---:|
|PD/p_dipole|35|2.1939841282838865e-5|
|PD/p_dipole_magnitude|32|5.6512653827667236e-5|
|PD/p_extensive|14|1.5497207641601563e-5|

The other10 fields/1440 observations all pass. Their largest maxima include
p_intensive4.76837158203125e-6, d_binary/d_intensive3.814697265625e-6,
p_pair4.0531158447265625e-6, d_atom2.1159648895263672e-6,
S/element_logits2.6226043701171875e-6, S/clean_bond_logits2.1457672119140625e-6,
S/coordinate5.801852367426363e-7, p_gradient5.644353180678241e-8 and
S/noise3.3074371227903576e-8.

|Transform|Dipole vector failures|Magnitude failures|Extensive failures|Total|
|---|---:|---:|---:|---:|
|General rotation|11|9|4|24|
|Translation only|16|14|4|34|
|Other rotation+translation|8|9|6|23|

|Dimension|Value|Case PASS/FAIL|
|---|---|---:|
|C1|C1-0|1/15|
|C1|C1-a|2/14|
|C1|C1-b|7/9|
|C3|two|5/19|
|C3|three|5/19|
|Head|H1_fixed|1/11|
|Head|H1_learned|4/8|
|Head|H2_fixed|2/10|
|Head|H3_fixed|3/9|
|Weight seed|20261026|7/17|
|Weight seed|20261027|3/21|

These are descriptive synthetic configuration counts, not D/P performance,
pretraining-seed SD or an architecture/head-selection rule. In particular they
cannot justify selecting C1-b or attenuating a head to pass the criterion.
Extensive failures occur under H1_fixed6/H2_fixed4/H3_fixed4; H1_learned has none.
Dipole failures occur across all four head policies.

## H0 and attribution limits

Saved H0 diagnostics are maxima over the whole44-clean-atom batch, not a separate
32-atom/channelwise difference. Across its cases/transforms C1-0 ranges
1.2516975402832031e-6..1.9073486328125e-6; C1-a
1.430511474609375e-6..1.6689300537109375e-6; C1-b
1.2665987014770508e-6..1.7583370208740234e-6.

The largest terminal failure is C1-0__three__H1_learned__seed20261027, other R+t,
p_dipole_magnitude, graph2: actual0.052897095680236816 versus
expected0.05284058302640915, error5.6512653827667236e-5. Its whole-clean-batch H0
maximum is1.430511474609375e-6. Small H0 drift amplified by extensive/dipole
readout and terminal arithmetic cancellation are both compatible with this
pattern. The JSON does not separate their causal contributions.

Source facts explain why compensated ordering alone can leave errors: the tree
rounds high+low back to FP32 (v3_numeric_stability.py:103); coordinate products are
rounded before compensated three-term addition (:127); the dipole multiplies
FP32 charges by FP32 centered coordinates (v3_heads.py:78-81); scalar readout
and H2/H3 nonlinear stages still consume FP32 pooled values (:193-194).
This is a mechanism hypothesis, not proof that a particular term caused a given
failure. Prior CPU1404's original-H0 FP64 head shadow also exceeded1e-5, so even
more accurate head arithmetic cannot be promised to resolve all current cases.

Only for the81 JSON-recorded failed argmax positions, the largest distance from
the expected scalar to its nearest FP32 value is1.4796939784567087e-8. At the
worst magnitude failure the expected value is exactly representable in FP32.
Thus these failures are not an established final-output quantization floor.
They do not prove all-FP32 arithmetic impossible or that the entire model must
use FP64. Better effective precision must preserve product residuals and low
parts across pooling/readout boundaries, rather than only reorder a rounded sum.
Any future precision change requires an explicit new protocol, not retrospective
acceptance, rescaling, changed weights/seeds/fixtures or a relaxed1e-5 threshold.

## Saved-input boundary for a terminal shadow

The52 archived arrays are only4(original+moved)x13 terminal outputs. JSON stores
H0 max/hash summaries and parameter digests, not actual cleanH0, charge/pooled
features or parameter tensors. Reading these existing NPZ files therefore cannot
supply a fixed-H0 complete terminal replay. CPU reconstruction of an encoder
would produce another H0 and must not be labelled the actual1435 GPU H0.
A separate capture is required unless another independently bound H0 artifact is
provided. A design-only capture/shadow plan is supplied separately; nothing ran.

## Bound sources

RESULT: /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/numeric_composed_GPU_v2_4521435/RESULT.json
RESULT bytes=216295; rawSHA256=29b011b7753800a694f251d5a2f9b22ab2a9044651343532bb7c6d2c02e41885.

All48 case JSON byte lengths and rawSHA256 were checked against the closed RESULT refs. No NPZ was opened.

|Case|Closed JSON relative path|Raw SHA256|
|---|---|---|
|C1-0__two__H1_fixed__seed20261026|cases/numeric_case_00/C1-0__two__H1_fixed__seed20261026__numeric_case.json|2f9beb18868383a715385460a28a4b23162ae1bf0c02ebba2a3ed4a752f09a17|
|C1-0__two__H1_fixed__seed20261027|cases/numeric_case_01/C1-0__two__H1_fixed__seed20261027__numeric_case.json|c9340f0742d581396c9df575d912843474192fb112aa5d7b0f571453ad6da9a4|
|C1-0__two__H1_learned__seed20261026|cases/numeric_case_02/C1-0__two__H1_learned__seed20261026__numeric_case.json|6271cee1b67674235903797782e256385540232f7a92a9ccee13095b41cd9cd4|
|C1-0__two__H1_learned__seed20261027|cases/numeric_case_03/C1-0__two__H1_learned__seed20261027__numeric_case.json|420dc3a136b930979d854a7d261094723633b69792be4a6b9341c7cb1b67451a|
|C1-0__two__H2_fixed__seed20261026|cases/numeric_case_04/C1-0__two__H2_fixed__seed20261026__numeric_case.json|20406159b4c8deb4d6c3107f1c60fe39d9bef3b5f8c59c514a250b3d7473600a|
|C1-0__two__H2_fixed__seed20261027|cases/numeric_case_05/C1-0__two__H2_fixed__seed20261027__numeric_case.json|84f0f18b112aeb8aeec900aae538eba0181e7f261f7b0251cb9364cbce3b1943|
|C1-0__two__H3_fixed__seed20261026|cases/numeric_case_06/C1-0__two__H3_fixed__seed20261026__numeric_case.json|7daba04afdd2cc36fb8efe1c0aed7bf7b109cd3181a7cd1e593ab1115f3f3fe2|
|C1-0__two__H3_fixed__seed20261027|cases/numeric_case_07/C1-0__two__H3_fixed__seed20261027__numeric_case.json|957ea2e6d763aae1d3cc6d68306726aad3dc84b55ece2289c923ba5fcaec6584|
|C1-0__three__H1_fixed__seed20261026|cases/numeric_case_08/C1-0__three__H1_fixed__seed20261026__numeric_case.json|e74da6b81551a417c5f025bd05259ccd99fb48c2d8dc34e42644cd1927e1234a|
|C1-0__three__H1_fixed__seed20261027|cases/numeric_case_09/C1-0__three__H1_fixed__seed20261027__numeric_case.json|6a4e47ea9f7faf9bbde9db5da243eb0f9935fe815713977e907d5e1fd03d5a25|
|C1-0__three__H1_learned__seed20261026|cases/numeric_case_10/C1-0__three__H1_learned__seed20261026__numeric_case.json|d865ebca3a90c3a5403ae4f086b7a61f7acb7f74169d861d9655f3296183cba4|
|C1-0__three__H1_learned__seed20261027|cases/numeric_case_11/C1-0__three__H1_learned__seed20261027__numeric_case.json|b084b3298417eb7120dceb66e10b2519267b59fd05fe3a5a0e2f28d3aa061036|
|C1-0__three__H2_fixed__seed20261026|cases/numeric_case_12/C1-0__three__H2_fixed__seed20261026__numeric_case.json|31965e3d98a0904f93c5debea85a10b7e2b0aaf72194ab7e0a0342a032dbfddd|
|C1-0__three__H2_fixed__seed20261027|cases/numeric_case_13/C1-0__three__H2_fixed__seed20261027__numeric_case.json|b8887b97369af8597a443d6bb3d3ef05822124e068350d321521d272bfdd70b2|
|C1-0__three__H3_fixed__seed20261026|cases/numeric_case_14/C1-0__three__H3_fixed__seed20261026__numeric_case.json|c5a0c26e83fc50d6b5d92c8bf68797d0553c754404299b0556c8ec78fc08fcc4|
|C1-0__three__H3_fixed__seed20261027|cases/numeric_case_15/C1-0__three__H3_fixed__seed20261027__numeric_case.json|cc35802bfb8fd065dc99883a2bd915bebe86200e771b54a616e9f152da2cfa02|
|C1-a__two__H1_fixed__seed20261026|cases/numeric_case_16/C1-a__two__H1_fixed__seed20261026__numeric_case.json|b050d74e243cee82d6e0de638ac8131852267e1e86094b45a03b800e6310df32|
|C1-a__two__H1_fixed__seed20261027|cases/numeric_case_17/C1-a__two__H1_fixed__seed20261027__numeric_case.json|9035aeea989c3b7767a31d29912ceca9d395ad1a8aa7e3a45c4734b865e76046|
|C1-a__two__H1_learned__seed20261026|cases/numeric_case_18/C1-a__two__H1_learned__seed20261026__numeric_case.json|51829f9b525962427e09938155e11f55f28986b5159643eff426cfb79145e94d|
|C1-a__two__H1_learned__seed20261027|cases/numeric_case_19/C1-a__two__H1_learned__seed20261027__numeric_case.json|5388d5b0154ccc64271a3894027d9ab9e1c970f3a4ee713005ebf6cec11be723|
|C1-a__two__H2_fixed__seed20261026|cases/numeric_case_20/C1-a__two__H2_fixed__seed20261026__numeric_case.json|00f5a69164a44a246ea586246bc6f2224a9c1f163774fc96e7d82ab0aa940178|
|C1-a__two__H2_fixed__seed20261027|cases/numeric_case_21/C1-a__two__H2_fixed__seed20261027__numeric_case.json|3a90d7cae3cb88d89cbd1df8cb77a0fcce6e11bd4404d3ec30955cbc55bc46cd|
|C1-a__two__H3_fixed__seed20261026|cases/numeric_case_22/C1-a__two__H3_fixed__seed20261026__numeric_case.json|101f08cbca124039d0faa8de176f1bbdfaaf6c5afbc67770ff6134f6c98effbb|
|C1-a__two__H3_fixed__seed20261027|cases/numeric_case_23/C1-a__two__H3_fixed__seed20261027__numeric_case.json|75f1f401d0795cdb0f8cdfb0f0db61152062c2a774d514ca17fa486eba0757a6|
|C1-a__three__H1_fixed__seed20261026|cases/numeric_case_24/C1-a__three__H1_fixed__seed20261026__numeric_case.json|5dedc162febe9b0935c27b83f821bfba16319297b094c2056202e2b29c3ab733|
|C1-a__three__H1_fixed__seed20261027|cases/numeric_case_25/C1-a__three__H1_fixed__seed20261027__numeric_case.json|707e43ec25c7c990f10a2a25d2007536b042b729112931a3ae39518e6a761754|
|C1-a__three__H1_learned__seed20261026|cases/numeric_case_26/C1-a__three__H1_learned__seed20261026__numeric_case.json|623697b3f764a3a2c546a8145954d9c9e5b96e18eafad8d884ea903ee690554a|
|C1-a__three__H1_learned__seed20261027|cases/numeric_case_27/C1-a__three__H1_learned__seed20261027__numeric_case.json|e40055c54bf70492980145e75d15f794a144ba7c94d8da6fedc0f6efa67b5aa8|
|C1-a__three__H2_fixed__seed20261026|cases/numeric_case_28/C1-a__three__H2_fixed__seed20261026__numeric_case.json|d6a012479802dd72cf9650702b0c3ef9d243443cfe3b99ae6faa9f336ab58e97|
|C1-a__three__H2_fixed__seed20261027|cases/numeric_case_29/C1-a__three__H2_fixed__seed20261027__numeric_case.json|76ade3af2d5ce3d433dd500c39efe9029cd9655245922cd4cead2d1259563b78|
|C1-a__three__H3_fixed__seed20261026|cases/numeric_case_30/C1-a__three__H3_fixed__seed20261026__numeric_case.json|a59d52ee0805690a8fea7fef4856193a0b28f191f500263b63768f805bcf85e8|
|C1-a__three__H3_fixed__seed20261027|cases/numeric_case_31/C1-a__three__H3_fixed__seed20261027__numeric_case.json|04cf6e0091bca804a0742972dee38fa573a272f28af5a431724eb37be8665f52|
|C1-b__two__H1_fixed__seed20261026|cases/numeric_case_32/C1-b__two__H1_fixed__seed20261026__numeric_case.json|533928d8848dec0e68a6ea80b13f4daaa21a5f4d3f43b75f3d39332bff52b33c|
|C1-b__two__H1_fixed__seed20261027|cases/numeric_case_33/C1-b__two__H1_fixed__seed20261027__numeric_case.json|2af4d094e4da1bfb42f29646a4e5616d2f0fd9c0546078f712be5e7883b0184e|
|C1-b__two__H1_learned__seed20261026|cases/numeric_case_34/C1-b__two__H1_learned__seed20261026__numeric_case.json|acf85fe5b025297d1ecf13c71ceb84ddeb71d21a3c9eacb629bfa0912a1cc8bb|
|C1-b__two__H1_learned__seed20261027|cases/numeric_case_35/C1-b__two__H1_learned__seed20261027__numeric_case.json|505aa20b1eab21d2dba0d6416eb7f0fc4813e5a0fd8ebef709930da64766241d|
|C1-b__two__H2_fixed__seed20261026|cases/numeric_case_36/C1-b__two__H2_fixed__seed20261026__numeric_case.json|91de845b3b3458d0ee7907b3727a5ea964ec9a2bce566f675f2de096b5f26bb5|
|C1-b__two__H2_fixed__seed20261027|cases/numeric_case_37/C1-b__two__H2_fixed__seed20261027__numeric_case.json|9b376b5d98c46208cfc3b292eb40d59718d5ed3604f991f3aa1cec7cf564048b|
|C1-b__two__H3_fixed__seed20261026|cases/numeric_case_38/C1-b__two__H3_fixed__seed20261026__numeric_case.json|a809174a9e8b69559bcdda316f996be6e4ef28ba9e7e64948c7ec7b238cb21eb|
|C1-b__two__H3_fixed__seed20261027|cases/numeric_case_39/C1-b__two__H3_fixed__seed20261027__numeric_case.json|2c9ab645c65ef19a30344f778f905498b72253d3b75376f104bcbefec888ebe3|
|C1-b__three__H1_fixed__seed20261026|cases/numeric_case_40/C1-b__three__H1_fixed__seed20261026__numeric_case.json|25cde77344426b11a47bed3950976edb2be64d870bbf117b9727ba38a70195b7|
|C1-b__three__H1_fixed__seed20261027|cases/numeric_case_41/C1-b__three__H1_fixed__seed20261027__numeric_case.json|2933466dc6fcf99dc3a19613053f7d6a78b628a996f33f76bbbaef079f30a2bc|
|C1-b__three__H1_learned__seed20261026|cases/numeric_case_42/C1-b__three__H1_learned__seed20261026__numeric_case.json|7af315f3d56df2ae29f6755e375db73c9cde3deed1e0d451ad704ace566d2625|
|C1-b__three__H1_learned__seed20261027|cases/numeric_case_43/C1-b__three__H1_learned__seed20261027__numeric_case.json|5b55c4218a14c36f31902288c8b3bd09e90ef3a358b663150379d555523c3e5d|
|C1-b__three__H2_fixed__seed20261026|cases/numeric_case_44/C1-b__three__H2_fixed__seed20261026__numeric_case.json|011e9be9b759f073d6ee0156076da364103a4603efec5f6584647d74d88a0201|
|C1-b__three__H2_fixed__seed20261027|cases/numeric_case_45/C1-b__three__H2_fixed__seed20261027__numeric_case.json|40c70dac8013a37272a82afddc698d54953c118a060639e4e75df724a37d0346|
|C1-b__three__H3_fixed__seed20261026|cases/numeric_case_46/C1-b__three__H3_fixed__seed20261026__numeric_case.json|e5085944627ca5715f60322992eeb9d380e88b7bb3d3eaa6d4dd3c22e6c735fc|
|C1-b__three__H3_fixed__seed20261027|cases/numeric_case_47/C1-b__three__H3_fixed__seed20261027__numeric_case.json|7cf42eb40ca0924ee8c26bd777616536101a559d626a8955c1164592c1011a47|

