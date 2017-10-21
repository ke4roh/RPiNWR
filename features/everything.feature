Feature: Weather Radio
  The radio does stuff when a storm system comes through

  Scenario: Storm passes through, internet and radio function normally
    Given the National Weather Service publishes alerts to the web 15 seconds after the radio
    Given a radio at 35.77N, 78.64E in 037183 monitoring text alerts from the web
    When the NWS issues a Tornado Watch for my area
    Then the alert level on the radio goes up to 35 within 60 seconds
    Then the most urgent message on the radio is a TOA
    When the NWS issues a TOW for elsewhere
    Then the most urgent message on the radio is a TOA
    Then the alert level on the radio stays at 35 for 60 seconds
    When the NWS updates the TOW to include my location
    Then the alert level on the radio goes up to 45 within 60 seconds
#    When the NWS updates the TOW area to <polygon> # overlapping my location
#    Then the alert level on the radio goes to 40 within 15 seconds
#    Then the most urgent message on the radio is a TOW
#    When the NWS updates the TOW area to <polygon> # not overlapping my location
