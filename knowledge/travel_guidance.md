# SmartTrip AI Local Travel Knowledge

## Train timetable versus fare
The RailRadar trains-between-stations endpoint supplies train timetable data for a selected station pair. It does not supply ticket fare or booking availability. Never claim a train is within a user's budget without a trusted fare source. Tell users to verify fares with an official booking provider.

## Station and route validation
Prefer exact station codes returned by the station search API. Verify the provider response origin and destination station codes against the requested station pair. Train names can describe the train's full route and do not alone prove that the selected station segment is incorrect. Use the segment departure, arrival, day, sequence, and duration fields when available.

## Travel date and overnight journeys
The selected date is interpreted as the train's date at the requested departure station. For overnight journeys, arrival may occur on the following day. Explain date changes clearly and do not silently change the requested date.

## Responsible travel recommendations
Timetable results are not a booking confirmation. Users should verify schedules, platform information, fare, seat availability, cancellation terms, and any service changes with the official provider before travelling or paying.

## Bus and flight data
If no live bus or flight provider is configured, do not present demo examples as live schedules. State that those modes are not live-integrated.
