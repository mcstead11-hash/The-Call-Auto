"""Send queued posts once the play's page is live. Run after the site has redeployed."""
import json
import os

from . import run, social


def main():
    state = run.load_state()
    for pid in list(state['pending_posts']):
        path = os.path.join(run.DRAFTS, pid + '.json')
        with open(path) as f:
            rec = json.load(f)
        detected = run._iso(run.page.load_plays()['plays'].get(pid, {}).get('auto', {}).get('detected'))
        if detected and run.now() - detected > run.dt.timedelta(hours=2):
            rec['results'] = 'expired: not posted, the call is over two hours old'
        else:
            rec['results'] = social.publish(rec['drafts'])
        with open(path, 'w') as f:
            json.dump(rec, f, indent=2)
        print(pid, rec['results'])
        state['pending_posts'].remove(pid)
    run.save_state(state)


if __name__ == '__main__':
    main()
