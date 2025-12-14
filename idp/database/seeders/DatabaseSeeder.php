<?php

namespace Database\Seeders;

use App\Models\User;
// use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;
use App\Models\Workspace;

class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        // User::factory(10)->create();

        User::factory()->create([
            'name' => 'Admin',
            'email' => 'admin@example.com',
            'password' => '123456789'
        ]);

                // Create workspaces
        $workspaces = Workspace::factory()->count(5)->create();

        // Create users and assign to workspaces
        $users = User::factory()->count(20)->create();

        foreach ($users as $user) {
            $workspace = $workspaces->random();
            $user->workspaces()->attach($workspace->id, [
                'role' => fake()->randomElement(['admin', 'member', 'viewer']),
                'created_at' => now()
            ]);
            
            // Set primary workspace for some users
            if (fake()->boolean(70)) {
                $user->update(['primary_workspace_id' => $workspace->id]);
            }
        }
    }
}
