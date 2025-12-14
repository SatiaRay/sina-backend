<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\GenerateClientTokenController;
use App\Http\Middleware\AuthorizeClientCredentials;

Route::get('/user', function (Request $request) {
    return $request->user();
})->middleware('auth:api');

/**
 * Client -> Machine login and register endpoints
 */
Route::post('/register', [AuthController::class, 'register']);
Route::post('/login', [AuthController::class, 'login']);

/**
 * Machine -> Machine auth endpoints
 */
Route::name('internal.')->prefix('/internal')->group(function () {
    Route::post('/client-token', GenerateClientTokenController::class)->middleware([AuthorizeClientCredentials::class])->name('client-token');
});

/**
 * Protected routes
 */
Route::middleware('auth:api')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout']);
    // Other authenticated API routes
});

Route::apiResource('/users', App\Http\Controllers\API\UserController::class);
