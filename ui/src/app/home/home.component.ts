import {Component, OnInit, NgZone, OnDestroy} from '@angular/core';
import { HomeService} from './home.service';
import { SettingsService } from '../settings/settings.service';

const electron = ( window as any ).require('electron');


@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit, OnDestroy {

  serverStatus: string;
  refreshServerStatus: any;

  directoryStatus: string;
  databaseStatus: string;
  pythonStatus: string;

  scenarioRunStatus: [][];
  refreshRunStatus: any;

  scenarioValidationStatus: [][];
  refreshValidationStatus: any;

  constructor(
    private homeService: HomeService,
    private settingsService: SettingsService,
    private zone: NgZone
  ) { }

  ngOnInit() {
    // Get the server status and refresh every 5 seconds
    this.getServerStatus();
    this.refreshServerStatus = setInterval(() => {
        this.getServerStatus();
    }, 5000);

    // Get setting status
    this.getDirectoryStatus();
    this.getDatabaseStatus();
    this.getPythonStatus();

    // If any of the settings are null, we'll overwrite the status from
    // the settings service with 'not set'
    // Ask Electron for the current settings
    electron.ipcRenderer.send('requestStoredSettings');
    electron.ipcRenderer.on('sendStoredSettings',
      (event, data) => {
        console.log('Got data ', data);
        if (data.requestedScenariosDirectory.value == null) {
          this.zone.run(() => this.directoryStatus = 'not set');
        }
        if (data.requestedGridPathDatabase.value === null) {
          this.zone.run(() => this.databaseStatus = 'not set');
        }
        if (data.requestedPythonEnvironment.value === null) {
          this.zone.run(() => this.pythonStatus = 'not set');
        }
      }
    );

    // Scenario run status
    this.getScenarioRunStatus();
    this.refreshRunStatus = setInterval(() => {
        this.getScenarioRunStatus();
    }, 5000);

    // Scenario validation status
    this.getScenarioValidationStatus();
    this.refreshValidationStatus = setInterval(() => {
        this.getScenarioValidationStatus();
    }, 5000);
  }

  ngOnDestroy() {
    // Clear status refresh intervals (stop refreshing) on component destroy
    clearInterval(this.refreshServerStatus);
    clearInterval(this.refreshRunStatus);
    clearInterval(this.refreshValidationStatus);
  }

  getServerStatus(): void {
    this.homeService.getServerStatus()
      .subscribe(
        status => this.serverStatus = status,
        error => {
          console.log('HTTP Error caught', error);
          this.serverStatus = 'down';
        }
      );
  }

  getDirectoryStatus(): void {
    this.settingsService.directoryStatusSubject
      .subscribe((settingsStatus: string) => {
        this.directoryStatus = settingsStatus;
      }
    );
  }

  getDatabaseStatus(): void {
    this.settingsService.databaseStatusSubject
      .subscribe((settingsStatus: string) => {
        this.databaseStatus = settingsStatus;
      }
    );
  }

  getPythonStatus(): void {
    this.settingsService.pythonStatusSubject
      .subscribe((settingsStatus: string) => {
        this.pythonStatus = settingsStatus;
      }
    );
  }

  getScenarioRunStatus(): void {
    this.homeService.getRunStatus()
      .subscribe(
        status => this.scenarioRunStatus = status
      );
  }

  getScenarioValidationStatus(): void {
    this.homeService.getValidationStatus()
      .subscribe(
        status => this.scenarioValidationStatus = status
      );
  }
}
