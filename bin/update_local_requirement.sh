#! /bin/bash
#
# Updates `saltbox-sdk` commit hash to current in requirements.
# Run from outer repo e. g.:
#
#   $ cd ~/sources/satlbox-core/
#   $ ../saltbox-sdk/bin/update_saltbox_sdk_requirements.sh
#

set -e

local_requirements_basename='local_requirements.txt'

local_requirements_file=$(find . -name "$local_requirements_basename")

if [ -z "$local_requirements_file" ]; then
  local_requirements_file='pyproject.toml'
fi

if [ -z "$local_requirements_basename" ]; then
  echo "No local requirements file candidate found" >&2
  exit 1
fi

saltbox_sdk_dir=$(dirname "$(dirname "$0")")

pushd "$saltbox_sdk_dir" > /dev/null
last_hash=$(git log -n 1 --pretty='format:%H')
popd > /dev/null

sed --in-place "s/\(saltbox-sdk @ .*@\)[a-zA-Z0-9]*\(.*\)/\1${last_hash}\2/" "$local_requirements_file"

git diff "$local_requirements_file"
