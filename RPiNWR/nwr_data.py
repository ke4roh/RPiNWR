_SAME_TRANSMITTERS = {
    "WXL58": {
        "counties": '037001-037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185'.split(
            '-'),
        "wfo": "KRAH",
        "frequency": 162.55

    },
    "WXL29": {
        "counties": ('032013', '032027'),
        "wfo": "KLKN",
        "frequency": 162.4
    },
    "WNG706": {
        "counties": "037063-037069-037085-037101-037127-037183-037191-037195".split('-'),
        "wfo": "KRAH",
        "frequency": 162.45
    },
    "KID77": {
        "counties": "020045-020091-020103-020121-020209-029037-029047-029095-029101-029107-029165-029177".split('-'),
        "wfo": "KEAX",
        "frequency": 162.55
    }
    "KEC55": {
        "counties": "048035-048085-048113-048121-048139-048143-048217-048221-048251-048367-048425-048439-048497".split('-'),
        "wfo": "KDFW",
        "frequency": 162.55
    }
    "KEC56": {
        "counties": "048035-048085-048113-048121-048139-048217-048221-048231-048257-048367-048397-048439".split('-'),
        "wfo": "KDFW",
        "frequency": 162.4
    }
    "WXK27": {
        "counties": "048021-048031-048053-048055-048209-048287-048453-048491".split('-'),
        "wfo": "KAUS-KATT".split('-'),
        "frequency": 162.4
    }
    "WXK35": {
        "counties": "048027-048035-048099-048145-048217-048293-048309-048331-048395".split('-'),
        "wfo": "KACT",
        "frequency": 162.475
    }
    "WXK67": {
        "counties": "048013-048019-048029-048091-048187-048259-048325-048493".split('-'),
        "wfo": "KSAT",
        "frequency": 162.55
    }
    "WNG641": {
        "counties": "048055-048091-048187-048209".split('-'),
        "wfo": "KT20",
        "frequency": 162.475
    }
    "WWF91": {
        "counties": "048031-048053-048171-048299-048319".split('-'),
        "wfo": "KAQO",
        "frequency": 162.425
    }
}


def get_frequency(transmitter):
    # TODO make nwr_data scrape this from the web if it's not here
    return _SAME_TRANSMITTERS[transmitter]["frequency"]


def get_counties(transmitter):
    # TODO make nwr_data scrape this from the web if it's not here
    return _SAME_TRANSMITTERS[transmitter]["counties"]


def get_wfo(transmitter):
    # TODO Where is this data on the web?
    return _SAME_TRANSMITTERS[transmitter]["wfo"]
