# Fresh historical RQ2 audit
Source: `results\raw\security-20260722-140421-f4aee0f2\security_results.json`, SHA256 `43414d9ef880f419d401ff0bbafca789dea6f45082e49abfe7b555c1da493f60`.
Verified 30 trials × 8 scenarios = 240 outcomes, positive = invalid/tampered condition.
{
  "scenario": "ALL",
  "n": 240,
  "TP": 210,
  "TN": 30,
  "FP": 0,
  "FN": 0,
  "TPR": 1.0,
  "TPR_CP95": "[0.9825872917321363, 1.0]",
  "TNR": 1.0,
  "TNR_CP95": "[0.8842966917779722, 1.0]",
  "FPR": 0.0,
  "FPR_CP95": "[0.0, 0.11570330822202779]",
  "FNR": 0.0,
  "FNR_CP95": "[0.0, 0.01741270826786368]"
}
Class-stratified exact two-sided Clopper–Pearson intervals are in rq2_confusion_matrix.csv.
Trials reuse a scenario construction; binomial intervals do not establish independent attack diversity.
S1 model weights; S2 tokenizer; S3 dataset manifest; S9a malformed signature plus unauthorized keyid;
S9b unauthorized signer; S9c missing model digest; S9d external model substitution.
SIGNATURE_AUTHENTICITY_NOT_TESTED_BY_S9A: source sets keyid=invalid; authorization precedes ECDSA.
Gate maps UNAUTHORIZED_SIGNER to its authorization failure. Historical decisions alone do not prove cryptographic execution.
New extensions are separate from these 240 outcomes.
