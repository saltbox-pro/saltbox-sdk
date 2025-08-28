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
saltbox_sdk_dir=$(dirname "$(dirname "$0")")

pushd "$saltbox_sdk_dir" > /dev/null
last_hash=$(git log -n 1 --pretty='format:%H')
popd > /dev/null

sed --in-place "s/\(saltbox-sdk @ .*@\).*/\1${last_hash}/" "$local_requirements_file"

git diff "$local_requirements_file"
