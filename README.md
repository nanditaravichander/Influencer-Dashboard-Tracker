# Influencer performance dashboard (Streamlit)

Upload an Excel workbook and the dashboard recalculates: KPIs, monthly trends, tier / platform / campaign
performance, top creators, community growth against a target, and ASA disclosure compliance.

## Files
| File | Purpose |
|---|---|
| `app.py` | The Streamlit app |
| `logic.py` | Data cleaning and metric calculations |
| `sample_data.py` | Generates fictional demo data (shown until you upload a file) |
| `influencer-data-template.xlsx` | Blank template to fill in with your own data |
| `sample-data.xlsx` | Example workbook (fictional) to test an upload |
| `requirements.txt` | Python packages |
| `make_template.py` | Optional: rebuilds the two Excel files |

## Run it on your computer
```
pip install -r requirements.txt
streamlit run app.py
```

## Publish it free on Streamlit Community Cloud
1. Create a free GitHub account and a **new repository**. Upload every file in this folder.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, pick the repository, set the main file to `app.py`, and deploy.
4. After a minute or two you get a public link like `https://your-name.streamlit.app` to put on your resume.

## Using it
1. Open the app. It starts with fictional sample data.
2. Fill in `influencer-data-template.xlsx` (delete the example row) and upload it in the sidebar.
3. Upload a new file whenever your data changes. The dashboard updates immediately.

## Important
- **Never commit real or confidential data to GitHub.** If the repo is public, anyone can read it. Upload real files through the app only; the app does not save them.
- Anyone with your app link can use it, and uploads are processed only for that visitor's session.
- Keep creator names anonymised (the sidebar tickbox does this) and round or scale confidential figures.
- Free apps go to sleep after inactivity. Open your link before an interview so it is awake.
