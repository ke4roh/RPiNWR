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
