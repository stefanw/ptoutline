import os
import getpass
import sys
import re
import glob
from collections import OrderedDict

import yaml
import requests
from lxml import html


BASE_URL = 'https://secure.pt-dlr.de/ptoutline/'

FORM_FIELDS = (
    ('wie_innovativ_ist_die_einge$00[]', -1),
    ('kommentar$00', ''),
    ('wie_gut_ist_der_bewerber_di$00[]', -1),
    ('kommentar$01', ''),
    ('wie_gro___ist_die_reichweit$00[]', -1),
    ('kommentar$02', ''),
    ('wie_hoch_ist_die_gesellscha$00[]', -1),
    ('kommentar$03', ''),
    ('wie_gut_finden_sie_persoenl$00[]', -1),
    ('kommentar$04', ''),
    ('welchen_fachlichen_ratschla$05', '-'),
)


def get_csrf(s):
    return {
        'csrf_test_name': s.cookies.get('csrf_live_appsites2'),
        'csrf_token_hash': s.cookies.get('csrf_live_appsites2')
    }


def login(s, username, password):
    s.get(BASE_URL + 'expert/prototypefund3')
    d = get_csrf(s)
    d.update({
        'email': username,
        'password': password
    })
    response = s.post(BASE_URL + 'expert/users/login/prototypefund3', data=d)
    if 'Logout' not in response.text:
        raise Exception('Login failed')


def get_survey_path(survey_id):
    base_path = os.getcwd()
    return os.path.join(base_path, 'round_%s' % survey_id)


def get_project_path(survey_path, project_id, slug):
    return os.path.join(survey_path, '%s-%s.pdf' % (project_id, slug))


def get_project_filepath(survey_path, project_id, ext='yml'):
    files = glob.glob(os.path.join(survey_path, '%s-*.%s' % (project_id, ext)))
    return files[0]


def get_project_id(row):
    project_id = row.xpath('./td[1]/a')[0].text_content().strip()
    if '-' in project_id:
        project_id = project_id.split('-')[1]
    return project_id


def get_project_rows(session, survey_id):
    response = session.get(BASE_URL + 'expert/surveys/index/%s' % survey_id)
    doc = html.fromstring(response.content)
    return doc.xpath('.//table[@id="content_table"]/tbody/tr')


def download_project(session, row, survey_path):
    project_id = get_project_id(row)
    print('Downloading project', project_id)

    tds = row.xpath('./td')
    title = str(tds[4].text_content()).strip()
    slug = re.sub('[\W\.\-]', '-', title)
    last_name = tds[5].text_content()
    first_name = tds[6].text_content()
    pdf_url = tds[2].xpath('.//a/@href')[0]
    pdf_response = session.get(pdf_url)
    pdf_path = get_project_path(survey_path, project_id, slug)
    if os.path.exists(pdf_path):
        print('Updating PDF:', pdf_path)

    with open(pdf_path, 'wb') as f:
        f.write(pdf_response.content)

    yaml_path = os.path.join(survey_path, '%s-%s.yml' % (project_id, slug))
    if not os.path.exists(yaml_path):
        with open(yaml_path, 'w') as f:
            data = OrderedDict([
                ('title', title),
                ('name', '%s %s' % (first_name, last_name)),
            ] + [val for val in FORM_FIELDS])
            for k, v in data.items():
                if isinstance(v, str):
                    v = '"%s"' % v
                f.write('%s: %s\n' % (k, v))
    else:
        print('Not overwriting YAML!!', yaml_path)


def download(session, survey_id):
    survey_path = get_survey_path(survey_id)
    os.makedirs(survey_path, exist_ok=True)

    for row in get_project_rows(session, survey_id):
        download_project(session, row, survey_path)


def load_post_data(survey_path, project_id):
    project_filepath = get_project_filepath(survey_path, project_id)
    with open(project_filepath) as f:
        post_data = yaml.load(f)

    post_data = {k: '' if v is None else str(v) for k, v in post_data.items()
                 if k not in ('title', 'name')}
    for k, v in post_data.items():

        if k.endswith('$00[]') and v not in ('0', '5', '10', '20'):
            raise ValueError('Project %s has bad value %s at %s' % (
                project_id, v, k))
    if not post_data['welchen_fachlichen_ratschla$05']:
        post_data['welchen_fachlichen_ratschla$05'] = '-'
    return post_data


def get_form_id(session, meta):
    data = get_csrf(session)
    data.update({
        'round_id': meta['round_id'],
        'expert_assignment_id': meta['expert_assignment_id'],
        'round_group_id': meta['round_group_id']
    })
    url = BASE_URL + 'expert/surveys/get/%s' % meta['round_id']
    response = session.post(url, data=data, headers={
        'X-Requested-With': 'XMLHttpRequest'
    })
    doc = html.fromstring(response.content)
    return doc.xpath('.//input[@name="form_id"]/@value')[0]


def get_meta_from_url(url):
    # e.g. PROTOTYPEFUND2-001/239/86447/508/Jury
    # round_id:239
    # expertassignment_id:86447
    # round_group_id:508
    parts = url.split('/')
    return {
        'round_id': parts[-4],
        'expert_assignment_id': parts[-3],
        'round_group_id': parts[-2],
    }


def save_project(session, row, survey_id, finalise=False):
    survey_path = get_survey_path(survey_id)

    link = row.xpath('./td[1]/a/@href')[0]
    meta = get_meta_from_url(link)

    form_id = get_form_id(session, meta)

    project_id = get_project_id(row)

    try:
        post_data = load_post_data(survey_path, project_id)
    except ValueError as e:
        print(e)
        return False

    print('Saving', project_id, 'with', meta['expert_assignment_id'], '...')
    data = get_csrf(session)
    data.update(post_data)
    data.update({
        'round_id': survey_id,
        'expert_assignment_id': meta['expert_assignment_id'],
        'form_id': form_id
    })
    if not finalise:
        url = BASE_URL + 'expert/surveys/save/%s/%s/%s' % (survey_id,
                                       meta['expert_assignment_id'], form_id)
        response = session.post(url, data=data, headers={
            'X-Requested-With': 'XMLHttpRequest'
        })
    else:
        url = BASE_URL + 'expert/surveys/finalize_survey/%s' % (survey_id,)
        response = session.post(url, data=data, headers={
            'X-Requested-With': 'XMLHttpRequest'
        })
    if response.status_code == 200:
        print('Saved')
        return True
    print('Save of %s failed!' % project_id)
    return False


def upload(session, survey_id, finalise=False):
    total = 0
    saved = 0
    for row in get_project_rows(session, survey_id):
        total += 1
        if save_project(session, row, survey_id, finalise=finalise):
            saved += 1
    if finalise:
        print('%d/%d sucessfully finalised' % (saved, total))
    else:
        print('%d/%d sucessfully saved' % (saved, total))


def main(command, survey_id, username):
    password = getpass.getpass()
    session = requests.Session()
    login(session, username, password)
    if command == 'upload':
        return upload(session, survey_id)
    elif command == 'download':
        return download(session, survey_id)
    if command == 'finalise':
        return upload(session, survey_id, finalise=True)
    else:
        print('Command not recognized')
        sys.exit(1)


if __name__ == '__main__':
    main(*sys.argv[1:])
