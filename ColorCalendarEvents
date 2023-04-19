/*
Purpose: Color code calendar events automatically, based on keywords
Author: Rachel Gramlich
Date Updated: 2023-04-19
Details: Adapted from https://www.linkedin.com/pulse/automate-color-coding-your-google-calendar-marguerite-thibodeaux-acc/?trk=articles_directory
        Color options found here: https://developers.google.com/apps-script/reference/calendar/event-color
*/

function ColorCalendarEvents() {
 
  var today = new Date();
  var nextmonth = new Date();
  nextmonth.setDate(nextmonth.getDate() + 31);
  Logger.log(today + " " + nextmonth);
 
  var calendars = CalendarApp.getAllOwnedCalendars();
  Logger.log("found number of calendars: " + calendars.length);
 
  for (var i=0; i<calendars.length; i++) {
    var calendar = calendars[i];
    var events = calendar.getEvents(today, nextmonth);
    for (var j=0; j<events.length; j++) {
      var e = events[j];
      var titlecase = e.getTitle();
      var title = titlecase.toLowerCase();
      var description = e.getDescription();

    //tentative
    if (title.slice(-1).includes("?")) {
       e.setColor(CalendarApp.EventColor.YELLOW);
      } 
  
    //fun
    if (title.includes("social:")) {
        e.setColor(CalendarApp.EventColor.MAUVE);
      }      
    if (title.includes("concert")) {
       e.setColor(CalendarApp.EventColor.MAUVE);
      }       
    if (title.includes("travel")) {
       e.setColor(CalendarApp.EventColor.MAUVE);
      }       
    if (title.includes("reservation")) {
       e.setColor(CalendarApp.EventColor.MAUVE);
      }  

    //appointments 
     if (title.includes("appt")) {
       e.setColor(CalendarApp.EventColor.CYAN);
      } 
    if (title.includes("workout")) {
       e.setColor(CalendarApp.EventColor.PALE_GREEN);
      } 
    if (title.includes("yoga")) {
       e.setColor(CalendarApp.EventColor.PALE_GREEN);
      }  
    if (title.includes("mota")) {
       e.setColor(CalendarApp.EventColor.PALE_GREEN);
      }  

    //reminders
    if (title.includes("to do:")) {
       e.setColor(CalendarApp.EventColor.PALE_RED);
      } 
    if (title.includes("errands")) {
       e.setColor(CalendarApp.EventColor.GREEN);
      }        
    if (title.includes("radar:")) {
       e.setColor(CalendarApp.EventColor.GRAY);
      }  
    }
  }
}
