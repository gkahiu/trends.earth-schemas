# -*- coding: utf-8 -*-

import os
import sys
import re
import shutil
import subprocess
from tempfile import mkstemp
import json
from datetime import datetime, timezone

from invoke import Collection, task


def get_version(c):
    with open(c.version_file_raw, 'r') as f:
        return f.readline().strip()

# Handle long filenames or readonly files on windows, see: 
# http://bit.ly/2g58Yxu
def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            try:
                os.remove(filename)
            except PermissionError:
                print('Permission error: unable to remove {}. Skipping that file.'.format(filename))
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except OSError:
                print('Unable to remove directory {}. Skipping removing that folder.'.format(os.path.join(root, name)))
    try:
        os.rmdir(top)
    except OSError:
        print('Unable to remove directory {}. Skipping removing that folder.'.format(top))


# Function to find and replace in a file
def _replace(file_path, regex, subst):
    #Create temp file
    fh, abs_path = mkstemp()
    if sys.version_info[0] < 3:
        with os.fdopen(fh,'w') as new_file:
            with open(file_path) as old_file:
                for line in old_file:
                    new_file.write(regex.sub(subst, line))
    else:
        with open(fh, 'w', encoding='Latin-1') as new_file:
            with open(file_path, encoding='Latin-1') as old_file:
                for line in old_file:
                    new_file.write(regex.sub(subst, line))
    os.remove(file_path)
    shutil.move(abs_path, file_path)


###############################################################################
# Misc development tasks (change version, deploy GEE scripts)
###############################################################################

@task(help={'v': 'Version to set'})
def set_version(c, v=None):
    # Validate the version matches the regex
    if not v:
        version_update = False
        v = get_version(c)
        print('No version specified, retaining version {}, but updating SHA and release date'.format(v))
    elif not re.match("[0-9]+([.][0-9]+)+", v):
        print('Must specify a valid version (example: 0.36)')
        return
    else:
        version_update = True
    
    release_date = datetime.now(timezone.utc).strftime('%Y/%m/%d %H:%M:%SZ')

    # Set in version.json
    print('Setting version to {} in version.json'.format(v))
    with open(c.version_file_details, 'w') as f:
        json.dump({"version": v, "release_date": release_date}, f,  indent=4)

    if version_update:
        # Set in version.txt
        print('Setting version to {} in {}'.format(v, c.version_file_raw))
        with open(c.version_file_raw, 'w') as f:
            f.write(v)

        # Set in setup.py
        print('Setting version to {} in setup.py'.format(v))
        setup_regex = re.compile("^([ ]*version=[ ]*')[0-9]+([.][0-9]+)+")
        _replace('setup.py', setup_regex, '\g<1>' + v)

@task()
def set_tag(c):
    v = get_version(c)
    ret = subprocess.run(['git', 'diff-index', 'HEAD', '--'], 
                          capture_output=True, text=True)
    if ret.stdout != '':
        ret = query_yes_no('Uncommitted changes exist in repository. Commit these?')
        if ret:
            ret = subprocess.run(['git', 'commit', '-m', 'Updating version tags for v{}'.format(v)])
            ret.check_returncode()
        else:
            print('Changes not committed - VERSION TAG NOT SET'.format(v))

    print('Tagging version {} and pushing tag to origin'.format(v))
    ret = subprocess.run(['git', 'tag', '-l', 'v{}'.format(v)], 
                         capture_output=True, text=True)
    ret.check_returncode()
    if 'v{}'.format(v) in ret.stdout:
        # Try to delete this tag on remote in case it exists there
        ret = subprocess.run(['git', 'push', 'origin', '--delete', 'v{}'.format(v)])
        if ret.returncode == 0:
            print('Deleted tag v{} on origin'.format(v))
    subprocess.check_call(['git', 'tag', '-f', '-a', 'v{}'.format(v), '-m', 'Version {}'.format(v)])
    subprocess.check_call(['git', 'push', 'origin', 'v{}'.format(v)])

###############################################################################
# Setup dependencies and install package
###############################################################################

def read_requirements():
    """Return a list of runtime and list of test requirements"""
    with open('requirements.txt') as f:
        lines = f.readlines()
    lines = [ l for l in [ l.strip() for l in lines] if l ]
    divider = '# test requirements'

    try:
        idx = lines.index(divider)
    except ValueError:
        raise BuildFailure(
            'Expected to find "{}" in requirements.txt'.format(divider))

    not_comments = lambda s,e: [ l for l in lines[s:e] if l[0] != '#']
    return not_comments(0, idx), not_comments(idx+1, None)

###############################################################################
# Options
###############################################################################

ns = Collection(set_version, set_tag)

ns.configure({
    'version_file_raw': 'version.txt',
    'version_file_details': 'version.json',
})
