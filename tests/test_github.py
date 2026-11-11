import io
import json
import unittest
import urllib.error
from steamdistics.github import GitHubClient, GitHubError, parse_remote


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RoutedOpener:
    def __init__(self, routes):
        self.routes = routes
        self.urls = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        for prefix, payload in self.routes.items():
            if prefix in request.full_url:
                if isinstance(payload, Exception):
                    raise payload
                return FakeResponse(json.dumps(payload).encode())
        raise AssertionError(f'sin ruta para {request.full_url}')


class GitHubClientTest(unittest.TestCase):
    def test_logins_por_sha_desde_compare_ignorando_commits_sin_cuenta(self):
        opener = RoutedOpener({'/compare/base...head': {'commits': [
            {'sha': 's1', 'author': {'login': 'anag'}},
            {'sha': 's2', 'author': None},
        ]}})
        client = GitHubClient('token', opener=opener)
        self.assertEqual(client.commit_logins('org', 'repo', 'head', 'base'), {'s1': 'anag'})

    def test_primer_tag_usa_la_lista_de_commits_paginada(self):
        full_page = [{'sha': f's{i}', 'author': {'login': 'anag'}} for i in range(100)]
        opener = RoutedOpener({'&page=1&': full_page, '&page=2&': [{'sha': 'last', 'author': {'login': 'beto'}}]})
        logins = GitHubClient('token', opener=opener).commit_logins('org', 'repo', 'head')
        self.assertEqual(len(logins), 101)
        self.assertIn('sha=head', opener.urls[0])

    def test_issues_excluye_pull_requests(self):
        opener = RoutedOpener({'/issues': [{'number': 1}, {'number': 2, 'pull_request': {}}]})
        self.assertEqual(GitHubClient('t', opener=opener).issues('org', 'repo'), [{'number': 1}])

    def test_team_inexistente_devuelve_none(self):
        not_found = urllib.error.HTTPError('u', 404, 'nf', {}, io.BytesIO(b''))
        opener = RoutedOpener({'/teams/': not_found})
        self.assertIsNone(GitHubClient('t', opener=opener).team_members('org', 'equipo'))

    def test_error_de_red_se_traduce_a_github_error(self):
        opener = RoutedOpener({'/issues': urllib.error.URLError('sin red')})
        with self.assertRaises(GitHubError):
            GitHubClient('t', opener=opener).issues('org', 'repo')


class ParseRemoteTest(unittest.TestCase):
    def test_remotos_ssh_y_https(self):
        for url in ('git@github.com:org/repo.git', 'https://github.com/org/repo', 'https://github.com/org/repo.git'):
            self.assertEqual(parse_remote(url), ('org', 'repo'), url)


if __name__ == '__main__':
    unittest.main()
