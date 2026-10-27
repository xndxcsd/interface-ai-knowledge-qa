# Website snapshots (not in git)

The five Dupaco website snapshot zips ship with the participant kit only. **Do not commit** unpacked pages or zips to this repository.

## For local evaluation

1. Obtain `snapshots_zip/` from the hackathon participant kit (five zips, oldest first).
2. Place that folder at the repository root (gitignored) **or** unzip to any path outside the repo.

3. Run:

   ```bash
   pip install -r requirements.txt
   python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl
   ```

On first run, the harness unpacks zips into `./snapshots/` (gitignored).

Or point at an existing unpack directory:

```bash
python3 harness/run_eval.py --submission . --snapshots /path/to/snapshots --eval eval/public_eval.jsonl
```
