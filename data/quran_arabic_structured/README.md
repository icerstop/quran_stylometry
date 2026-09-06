---
dataset_info:
  features:
  - name: surah_number
    dtype: int64
  - name: surah_name_ar
    dtype: string
  - name: surah_name_en
    dtype: string
  - name: revelation_type
    dtype: string
  - name: ayah_number_in_surah
    dtype: int64
  - name: ayah_number_total
    dtype: int64
  - name: text_arabic
    dtype: string
  - name: text_english
    dtype: string
  - name: page
    dtype: int64
  - name: is_sajda
    dtype: string
  - name: tafsir_ibn_kathir_en
    dtype: string
  splits:
  - name: train
    num_bytes: 42885534
    num_examples: 6236
  download_size: 6840327
  dataset_size: 42885534
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
---
