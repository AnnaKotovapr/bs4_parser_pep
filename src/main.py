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
from exceptions import ParserFindTagException


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
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append((version_link, h1.text, dl_text))

    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = soup.find_tag('div', {'class': 'sphinxsidebarwrapper'})
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
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)
    if response is None:
        return

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def get_pep_status(soup_pep):
    try:
        dl_tag = find_tag(
            soup_pep, 'dl', attrs={'class': 'rfc2822 field-list simple'}
        )

        if dl_tag is not None:
            status_pep = dl_tag.find(
                string='Status'
            ).parent.find_next_sibling('dd').string
    except ParserFindTagException as e:
        print(f"Error: {e}")
        status_pep = None
    return status_pep


def pep(session):

    response = get_response(session, PEPS_URL)
    if response is None:
        return

    soup = BeautifulSoup(response.text, features='lxml')
    section_tag = find_tag(soup, 'section', {'id': 'numerical-index'})
    tr_tags = section_tag.find_all('tr')

    log_messages = []
    status_sum = {}
    results = [('Статус', 'Количество')]

    for tr_tag in tqdm(tr_tags[1:]):
        pep_link = tr_tag.td.find_next_sibling().find('a')['href']
        pep_url = urljoin(PEPS_URL, pep_link)  # полная ссылка

        response_for_pep = get_response(session, pep_url)
        if response_for_pep is None:
            continue

        soup_pep = BeautifulSoup(response_for_pep.text, features='lxml')
        status_pep = get_pep_status(soup_pep)
        status_sum[status_pep] = status_sum.get(status_pep, 0) + 1

        if status_pep not in EXPECTED_STATUS[tr_tag.td.text[1:]]:
            error_message = (f'Несовпадающие статусы:\n'
                             f'{pep_url}\n'
                             f'Статус в карточке: {status_pep}\n'
                             f'Ожидаемые статусы: '
                             f'{EXPECTED_STATUS[tr_tag.td.text[1:]]}')
            log_messages.append(error_message)

    results.extend(status_sum.items())
    total_peps = sum(status_sum.values())
    results.append(('Total', total_peps))

    if log_messages:
        logging.warning('\n'.join(log_messages))

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
