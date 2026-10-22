import json, csv, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from scipy.stats import beta as betadist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# Load all 240 security results
with open('results/raw/security-20260722-140421-f4aee0f2/security_results.json') as f:
    results = json.load(f)

print("Total outcomes:", len(results))

# Tally by scenario
scenarios_seen = {}
for r in results:
    s = r['scenario_id']
    if s not in scenarios_seen:
        scenarios_seen[s] = {'count': 0, 'fp': 0, 'fn': 0, 'decisions': []}
    scenarios_seen[s]['count'] += 1
    if r.get('false_positive'): scenarios_seen[s]['fp'] += 1
    if r.get('false_negative'): scenarios_seen[s]['fn'] += 1
    scenarios_seen[s]['decisions'].append(r['decision'])

print("Scenarios found:", sorted(scenarios_seen.keys()))
for s in sorted(scenarios_seen.keys()):
    v = scenarios_seen[s]
    decisions_set = set(v['decisions'])
    print("  %s: n=%d, FP=%d, FN=%d, decisions=%s" % (s, v['count'], v['fp'], v['fn'], decisions_set))

# Define positive = invalid/tampered condition (not S0)
# S0 = legitimate deployment
legitimate_scenarios = {'S0'}
invalid_scenarios = {'S1','S2','S3','S9a','S9b','S9c','S9d'}

legitimate_results = [r for r in results if r['scenario_id'] in legitimate_scenarios]
invalid_results = [r for r in results if r['scenario_id'] in invalid_scenarios]

print("\nLegitimate (S0):", len(legitimate_results))
print("Invalid (S1,S2,S3,S9a,S9b,S9c,S9d):", len(invalid_results))

# Confusion matrix
TN = sum(1 for r in legitimate_results if r['decision'] == 'APPROVED' and not r.get('false_positive'))
FP = sum(1 for r in legitimate_results if r['decision'] != 'APPROVED' or r.get('false_positive'))
TP = sum(1 for r in invalid_results if r['decision'] != 'APPROVED' and not r.get('false_negative'))
FN = sum(1 for r in invalid_results if r['decision'] == 'APPROVED' or r.get('false_negative'))

print("\nConfusion matrix:")
print("  TP=%d, TN=%d, FP=%d, FN=%d" % (TP, TN, FP, FN))
print("  Total=%d" % (TP+TN+FP+FN))

TPR = TP/(TP+FN) if (TP+FN) > 0 else 0
TNR = TN/(TN+FP) if (TN+FP) > 0 else 0
FPR = FP/(FP+TN) if (FP+TN) > 0 else 0
FNR = FN/(FN+TP) if (FN+TP) > 0 else 0

print("  TPR=%.6f, TNR=%.6f, FPR=%.6f, FNR=%.6f" % (TPR, TNR, FPR, FNR))

# Clopper-Pearson CI
if HAS_SCIPY:
    n_fp_total, k_fp = FP+TN, FP
    if k_fp == 0:
        cp_fpr_lo = 0.0
        cp_fpr_hi = 1.0 - (0.025 ** (1.0/n_fp_total)) if n_fp_total > 0 else 1.0
        cp_fpr_hi_exact = float(betadist.ppf(0.975, 1, n_fp_total))
    else:
        cp_fpr_lo = float(betadist.ppf(0.025, k_fp, n_fp_total - k_fp + 1))
        cp_fpr_hi = float(betadist.ppf(0.975, k_fp + 1, n_fp_total - k_fp))
        cp_fpr_hi_exact = cp_fpr_hi

    n_fn_total, k_fn = FN+TP, FN
    if k_fn == 0:
        cp_fnr_lo = 0.0
        cp_fnr_hi_exact = float(betadist.ppf(0.975, 1, n_fn_total))
    else:
        cp_fnr_lo = float(betadist.ppf(0.025, k_fn, n_fn_total - k_fn + 1))
        cp_fnr_hi_exact = float(betadist.ppf(0.975, k_fn + 1, n_fn_total - k_fn))

    if k_fp == 0:
        print("\nClopper-Pearson 95%% CI for FPR: [0.000000, %.6f]" % cp_fpr_hi_exact)
    else:
        print("\nClopper-Pearson 95%% CI for FPR: [%.6f, %.6f]" % (cp_fpr_lo, cp_fpr_hi_exact))
    if k_fn == 0:
        print("Clopper-Pearson 95%% CI for FNR: [0.000000, %.6f]" % cp_fnr_hi_exact)
    else:
        print("Clopper-Pearson 95%% CI for FNR: [%.6f, %.6f]" % (cp_fnr_lo, cp_fnr_hi_exact))
else:
    print("scipy not available -- using exact formula for k=0")
    if FP == 0 and FN == 0:
        n_fp_total = FP+TN
        n_fn_total = FN+TP
        # One-sided: P(FP=0|n) at 95%, exact = 1 - 0.05^(1/n)
        cp_fpr_hi_exact = 1.0 - (0.05 ** (1.0/n_fp_total))
        cp_fnr_hi_exact = 1.0 - (0.05 ** (1.0/n_fn_total))
        print("\nClopper-Pearson 95%% CI for FPR: [0.000000, %.6f]" % cp_fpr_hi_exact)
        print("Clopper-Pearson 95%% CI for FNR: [0.000000, %.6f]" % cp_fnr_hi_exact)
