import logging
import re
from urllib.parse import urljoin

import requests
import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BASE_DIR, MAIN_DOC_URL
from constants import PEPS_URL, EXPECTED_STATUS
from configs import configure_argument_parser
from configs import configure_logging
from outputs import control_output
from utils import get_response, find_tag


def whats_new(session):
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = soup.find('dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append((version_link, h1.text, dl_text))

    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = soup.find('div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    main_tag = soup.find('div', {'role': 'main'})
    table_tag = main_tag.find('table', {'class': 'docutils'})
    pdf_a4_tag = table_tag.find('a', {'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):

    response = get_response(session, PEPS_URL)
    if response is None:
        return

    soup = BeautifulSoup(response.text, features='lxml')
    section_tag = soup.find('section', {'id': 'numerical-index'})
    tr_tags = section_tag.find_all('tr')

    status_sum = {}
    total_peps = 0

    for tr_tag in tqdm(tr_tags[1:]):
        total_peps += 1
        pep_link = tr_tag.td.find_next_sibling().find('a')['href']
        pep_url = urljoin(PEPS_URL, pep_link)  # полная ссылка

        response_for_pep = get_response(session, pep_url)
        if response_for_pep is None:
            return

        soup_pep = BeautifulSoup(response_for_pep.text, features='lxml')

        dl_tag = soup_pep.find(
            'dl', attrs={'class': 'rfc2822 field-list simple'}
        )

        if dl_tag is not None:
            status_pep = dl_tag.find(
                string='Status'
            ).parent.find_next_sibling('dd').string

        if status_pep in status_sum:
            status_sum[status_pep] += 1
        if status_pep not in status_sum:
            status_sum[status_pep] = 1
        if status_pep not in EXPECTED_STATUS[tr_tag.td.text[1:]]:
            error_message = (f'Несовпадающие статусы:\n'
                             f'{pep_url}\n'
                             f'Статус в карточке: {status_pep}\n'
                             f'Ожидаемые статусы: '
                             f'{EXPECTED_STATUS[tr_tag.td.text[1:]]}')
            logging.warning(error_message)

    results = [('Статус', 'Количество')]

    for status in status_sum:
        results.append((status, status_sum[status]))
    results.append(('Total', total_peps))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')
    session = requests_cache.CachedSession()

    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')
    session = requests.Session()


if __name__ == '__main__':
    main()
