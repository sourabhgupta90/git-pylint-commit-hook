#!/usr/bin/python
# -*- coding: utf-8 -*-
""" Commit hook for pylint """

import decimal
import os
import re
import sys
import subprocess
import collections
import ConfigParser
import json

ExecutionResult = collections.namedtuple('ExecutionResult',
        'status, stdout, stderr')


def _execute(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    (stdout, stderr) = process.communicate()
    status = process.poll()
    return ExecutionResult(status, stdout, stderr)


def _current_commit():
    if _execute('git rev-parse --verify HEAD'.split()).status:
        return '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    else:
        return 'HEAD'


def _get_list_of_committed_python_files():
    """ Returns a list of files about to be commited. """

    files = []

    # pylint: disable=E1103

    diff_index_cmd = 'git diff-index %s' % _current_commit()
    output = subprocess.check_output(diff_index_cmd.split())
    for result in output.split('\n'):
        if result != '':
            result = result.split()
            if result[4] in ['A', 'M']:
                if _is_python_file(result[5]):
                    files.append((result[5], None))  # None is initial score

    return files


def _get_user():
    """
    Returns user
    """

    get_user_cmd = 'git var GIT_AUTHOR_IDENT '
    user = subprocess.check_output(get_user_cmd.split())
    return user.split()[0]


def _is_python_file(filename):
    """Check if the input file looks like a Python script

    Returns True if the filename ends in ".py" or if the first line
    contains "python" and "#!", returns False otherwise.

    """

    if filename.endswith('.py'):
        return True
    else:
        with open(filename, 'r') as file_handle:
            first_line = file_handle.readline()
        return 'python' in first_line and '#!' in first_line


_SCORE_REGEXP = \
    re.compile(r'^Your\ code\ has\ been\ rated\ at\ (\-?[0-9\.]+)/10')


def _parse_score(pylint_output):
    """Parse the score out of pylint's output as a float

    If the score is not found, return 0.0.

    """

    for line in pylint_output.splitlines():
        match = re.match(_SCORE_REGEXP, line)
        if match:
            return float(match.group(1))
    return 0.0


def _is_empty_init_file(python_file):
    """
    Checking empty init file
    """

    if os.path.basename(python_file) == '__init__.py':
        if os.stat(python_file).st_size == 0:
            return True
    return False


def _get_git_previous_commit():
    """
    Getting last commit SHA
    """

    diff_index_cmd = 'git log -n 1 --pretty=format:%h'
    output = subprocess.check_output(diff_index_cmd.split())
    return output


def _get_commit_file_data(git_file, commit_sha='HEAD~1'):
    """
    get previous commit git file data
    """

    try:
        diff_index_cmd = 'git show %s:%s' % (commit_sha, git_file)
        output = subprocess.check_output(diff_index_cmd.split())
    except Exception, e:
        output = ''
    return output


def _run_subprocess(process_command):
    """
     run subprocess in python
    """

    try:
        diff_index_cmd = process_command
        output = subprocess.check_output(diff_index_cmd.split())
    except Exception, e:
        output = ''
    return output


_GIT_PYLINT_MINIMUM_SCORE = 4


def _get_prev_score(pylint, python_files, commit_sha='HEAD~1'):
    total_score = 0
    checked_pylint_files = 0
    avg_score = 0
    for (python_file, score) in python_files:
        if _is_empty_init_file(python_file):
            continue
        git_commit_file_name = 'pylint_' + python_file.split('/')[-1]
        git_commit_file = '/'.join(python_file.split('/')[:-1]
                                   + [git_commit_file_name])
        f = open(git_commit_file, 'w')
        f.write(_get_commit_file_data(python_file, commit_sha))
        f.close()
        (out, _) = _run_pylint(pylint, git_commit_file)
        os.remove(git_commit_file)
        if _parse_score(out):
            score = _parse_score(out)
            total_score += score
            checked_pylint_files += 1
    if checked_pylint_files:
        avg_score = total_score / checked_pylint_files
    if avg_score == 0:
        avg_score = _GIT_PYLINT_MINIMUM_SCORE
    return avg_score


def _run_pylint(pylint, python_file, suppress_report=False):
    try:
        command = [pylint]

        penv = os.environ.copy()
        penv['LANG'] = 'it_IT.UTF-8'
        penv['LC_CTYPE'] = 'it_IT.UTF-8'
        penv['LC_COLLATE'] = 'it_IT.UTF-8'
        """
        if pylint_params:
            command += pylint_params.split()
            if '--rcfile' not in pylint_params:
                command.append('--rcfile={}'.format(pylintrc))
        else:
            command.append('--rcfile={}'.format(pylintrc))
        """

        command.append(python_file)

        if suppress_report:
            command.append('--reports=n')
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=penv)
        (out, _value) = proc.communicate()
    except OSError:
        print '\nAn error occurred. Is pylint installed?'
        sys.exit(1)
    return (out, _value)


def _process_git_log_data(git_log_data):
    """
    parse and process git log data 
    """

    git_log_commit = []
    for each_commit in git_log_data.split('\n'):
        git_log_commit.append(json.loads(each_commit))
    return git_log_commit


def _repo_score():
    """
    Calculate git repo score.
    """

    gitlogs = \
        'git log -n 4 --pretty=format:{"commit":"%H","user":"%an"}'
    git_log_output = _run_subprocess(gitlogs)

    process_git_log_data = _process_git_log_data(git_log_output)
    list_of_commit_score = []
    for i in xrange(0, len(process_git_log_data) - 1):
        commit_score = 0
        commit = process_git_log_data[i]['commit']
        prev_commit = process_git_log_data[i + 1]['commit']
        file_changed = \
            'git log  --name-only --pretty=format:%f {0}..{1}'.format(prev_commit,
                commit)
        file_changed_info = _run_subprocess(file_changed)
        file_changed_list = file_changed_info.split('\n')[1:]
        for changed_file in file_changed_list:
            file_score = _get_prev_score('pylint', [(changed_file,
                    None)], commit)
            prev_file_score = _get_prev_score('pylint', [(changed_file,
                    None)], prev_commit)
            commit_score += file_score - prev_file_score
        list_of_commit_score.append({process_git_log_data[i]['commit'
                                    ]: commit_score})
    print list_of_commit_score


def check_repo(
    limit,
    pylint='pylint',
    pylintrc='.pylintrc',
    pylint_params=None,
    suppress_report=False,
    datfile='/tmp/git.dat',
    scorefile='/tmp/scores.dat',
    ):
    """ Main function doing the checks

    :type limit: float
    :param limit: Minimum score to pass the commit
    :type pylint: str
    :param pylint: Path to pylint executable
    :type pylintrc: str
    :param pylintrc: Path to pylintrc file
    :type pylint_params: str
    :param pylint_params: Custom pylint parameters to add to the pylint command
    :type suppress_report: bool
    :param suppress_report: Suppress report if score is below limit
    """

    # List of checked files and their results

    python_files = _get_list_of_committed_python_files()

    # Set the exit code

    all_filed_passed = True

    total_score = 0.0

    # Don't do anything if there are no Python files

    if len(python_files) == 0:
        sys.exit(0)

    # Load any pre-commit-hooks options from a .pylintrc file (if there is one)

    if os.path.exists(pylintrc):
        conf = ConfigParser.SafeConfigParser()
        conf.read(pylintrc)
        if conf.has_option('pre-commit-hook', 'command'):
            pylint = conf.get('pre-commit-hook', 'command')
        if conf.has_option('pre-commit-hook', 'params'):
            pylint_params += ' ' + conf.get('pre-commit-hook', 'params')
        if conf.has_option('pre-commit-hook', 'limit'):
            limit = float(conf.get('pre-commit-hook', 'limit'))

    # Pylint Python files

    i = 1
    n_files = len(python_files)
    for (python_file, score) in python_files:

        # Allow __init__.py files to be completely empty

        if _is_empty_init_file(python_file):
            print 'Skipping pylint on {} (empty __init__.py)..\tSKIPPED'.format(python_file)

            # Bump parsed files

            i += 1
            continue

        # Start pylinting

        sys.stdout.write('Running pylint on {} (file {}/{})..\t'.format(python_file,
                         i, n_files))
        sys.stdout.flush()
        (out, _) = _run_pylint(pylint, python_file)

        # Verify the score

        score = _parse_score(out)
        file_prev_score = _get_prev_score(pylint, [(python_file,
                score)])
        if file_prev_score and score >= file_prev_score:
            status = 'PASSED'
        elif score >= float(limit):
            status = 'PASSED'
        else:
            status = 'FAILED'
            all_filed_passed = False

        total_score += score

        # Add some output

        print '{:.2}/10.00\t{}'.format(decimal.Decimal(score), status)
        if 'FAILED' in status:
            (out, _) = _run_pylint(pylint, python_file,
                                   suppress_report=True)
            print out

        # Bump parsed files

        i += 1

    user = _get_user()

    prev_score = _get_prev_score(pylint, python_files)

    if 'FAILED' in status:
        new_score = total_score
    else:
        new_score = (total_score + prev_score) / (n_files + 1)

    impact = new_score - prev_score
    total_score = total_score / n_files


    print 'Total score ', str(total_score)
    print 'Your score made an impact of ', str(impact)



    return all_filed_passed


if __name__ == '__main__':
    _repo_score()

            