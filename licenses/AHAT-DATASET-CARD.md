---
license: cc-by-nc-4.0
dataset_info:
  features:
  - name: id
    dtype: string
  - name: tag
    dtype: string
  - name: instruction
    dtype: string
  - name: scene_graph
    dtype: string
  - name: plan
    sequence: string
  splits:
  - name: train
    num_bytes: 1136323361
    num_examples: 67125
  download_size: 178395907
  dataset_size: 1136323361
configs:
- config_name: default
  data_files:
  - split: train
    path: train/train-*
---

# 🧢 AHAT Dataset


This is the official dataset for the paper "Any House Any Task: Scalable Long-Horizon Planning for Abstract Human Tasks".

This dataset contains the abstract human instructions, textual scene graphs and plans used in the AHAT.


## 🛎️Dataset Details

- **Repository:** [AHAT github](https://github.com/Sii-liuzhihong/AHAT)
- **Paper:** [Any House Any Task: Scalable Long-Horizon Planning for Abstract Human Tasks](https://arxiv.org/abs/2602.12244)
- **Demo:** [AHAT accompanying video](https://www.youtube.com/watch?v=PopY2x01xdw)


## 📢 News
- **[2026-10-14]** The evaluation set is updated to **`ahat-eval-repaired-v5`**, including scene-containment repairs and the bathroom-sink correction.
- **[2026-04]**  We have released the **Evaluation Set** (`ahat_eval_set.jsonl`)!
- **[2026-04]**  We have released the full **Training Data** (`train/`) and the **base scenes data** (`ahat_base_scenes.jsonl`)! 


## 📂 Dataset Structure 

The dataset is organized as follows:

ahat_eval_set.jsonl: Comprises **348** tasks categorized into three difficulty tiers: easy, medium, and open.

ahat_base_scenes.jsonl: Contains **308** foundational textual scene graphs curated and processed from the HSSD and Gibson datasets.

train/: Includes **67.1k** training samples synthesized and solved using the methodology detailed in our paper. This is the primary dataset used for training the AHAT model.


## Evaluation set update

The current evaluation release is **`ahat-eval-repaired-v5`** (348 tasks). Use [`ahat_eval_set.jsonl`](ahat_eval_set.jsonl) with [`ahat_domain.pddl`](ahat_domain.pddl). File hashes and detailed repair records are in [`ahat_eval_manifest.json`](ahat_eval_manifest.json).

This release includes `can_be_lighted` annotations, reference-plan repairs at zero-based indices 182, 213, 222 and 305, action-format normalization at indices 157 and 275, and repairs to redundant scene ancestry and manually reviewed containment conflicts.

The latest data correction (2026-09-29) fixes zero-based index **132** (JSONL line 133, record ID `395a29fe-5348-4464-aab7-005a9037e774`): `sink_1` now starts with `is_clean=false`, and its reference plan has four actions, including navigation to the sink and `clean_furniture`, so it actually cleans the sink.

The domain fixes hand-state effects and constrains `light_on` with `can_be_lighted`. All 348 records pass scene-structure checks, forest construction, reference-plan replay and implemented state-consistency checks. The corrected task 132 also passes the sink-cleanliness outcome check. Instructions are unchanged; reference plans do not guarantee completion of every natural-language instruction. Earlier versions remain available in the repository history.

## 🚀 How to Use

We recommend using our official script to download the data selectively.

Clone the code repository:

```
git clone https://github.com/Sii-liuzhihong/AHAT
cd ahat
pip install -e .
```

Use the download script:
```
# For downloading evel_set
python scripts/download_data.py

# For downloading other data, please refer to the code above.
```

## 📚 Citation 

```bibtex
@article{liu2026ahat,
  title={Any House Any Task: Scalable Long-Horizon Planning for Abstract Human Tasks},
  author={Liu, Zhihong and Li, Yang and Huang, Rengming and Lu, Cewu and Cai, Panpan},
  journal={arXiv preprint arXiv:2602.12244},
  year={2026}
}
```
