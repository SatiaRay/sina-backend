<?php

namespace Database\Factories;

use Illuminate\Database\Eloquent\Factories\Factory;

class WorkspaceFactory extends Factory
{
    public function definition(): array
    {
        return [
            'id' => fake()->unique()->uuid(),
            'name' => fake()->company(),
            'plan' => fake()->randomElement(['free', 'pro', 'business']),
            'metadata' => json_encode(['color' => fake()->hexColor()]),
        ];
    }
}