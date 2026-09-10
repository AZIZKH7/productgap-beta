# ProductGap Customer Beta v0.6

Find what your competitors missed.

ProductGap takes three competing product URLs and returns:
- market score
- ranked product opportunities
- target buyer and positioning
- recommended product changes
- evidence trail
- validation tests
- kill conditions
- downloadable report

Local run:
`py -m pip install -r requirements.txt`
Create `.streamlit/secrets.toml` from the included example.
`py -m streamlit run app.py`

The customer's browser never receives your OpenAI API key. Store it only as a server secret.
