# PT-Outline Automator

Python script to download prototype fund surveys, upload and finalize answers at PT-Outline, an online survey tool of DLR.

- Downloads resources associated
- Allows offline editing in a YAML file
- Quick bulk upload your answers and 'finalise' them

## Install

Needs python3.


    pip3 install -r requirements.txt
    # or alternatively using pipenv
    pipenv --three
    pipenv install


## Usage

1. Find your Survey round number in the URL: <https://secure.pt-dlr.de/ptoutline/expert/surveys/index/279>
2. Run `python3 ptoutline.py download 279 <your-email>` and enter your password.
3. Find project PDFs and YAML files in a directory called `round_279`
4. Fill out all the YAML files. Ratings can be one of 0, 5, 10, 20 (higher is better).
5. Run `python3 ptoutline.py upload 279 <your-email>` to upload your answers.
6. To finalise everything run `python3 ptoutline.py finalise 279 <your-email>`
7. If you want to make changes after finalising repeat step 5 and 6
