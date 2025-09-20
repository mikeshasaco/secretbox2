#!/usr/bin/env python3
"""
Populate PlayerMapping table to link nflreadpy names to PrizePicks names
"""
from django.core.management.base import BaseCommand
from core.models import PlayerMapping, Player, PropLineHistory
import nflreadpy as nfl
from difflib import SequenceMatcher
import re


class Command(BaseCommand):
    help = 'Populate PlayerMapping table to link nflreadpy names to PrizePicks names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.8,
            help='Similarity threshold for name matching (0.0-1.0, default: 0.8)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']
        
        self.stdout.write("Loading player data for mapping...")
        
        # Get nflreadpy players
        nfl_players = nfl.load_players()
        nfl_players = nfl_players.filter(nfl_players['status'] == 'ACT')  # Only active players
        
        # Get PrizePicks player names from prop lines
        prizepicks_players = set(PropLineHistory.objects.values_list('player_name', flat=True).distinct())
        
        self.stdout.write(f"Found {len(nfl_players)} active NFL players")
        self.stdout.write(f"Found {len(prizepicks_players)} PrizePicks players")
        
        created_count = 0
        updated_count = 0
        
        # Process each nflreadpy player
        for nfl_player in nfl_players.iter_rows(named=True):
            nfl_name = nfl_player['display_name']
            position = nfl_player['position']
            current_team = nfl_player['latest_team']
            
            # Find best match in PrizePicks players
            best_match = self.find_best_match(nfl_name, prizepicks_players, threshold)
            
            if best_match:
                # Create player_id from PrizePicks name
                player_id = best_match.lower().replace(' ', '_').replace('.', '').replace("'", '')
                
                # Check if this player_id already exists for a different nflreadpy_name
                existing_mapping = PlayerMapping.objects.filter(player_id=player_id).first()
                if existing_mapping and existing_mapping.nflreadpy_name != nfl_name:
                    # Skip this mapping to avoid conflicts
                    if dry_run:
                        self.stdout.write(f"Would skip mapping: {nfl_name} → {best_match} (player_id conflict with {existing_mapping.nflreadpy_name})")
                    continue
                
                if dry_run:
                    self.stdout.write(f"Would create mapping: {nfl_name} → {best_match} ({current_team})")
                else:
                    mapping, created = PlayerMapping.objects.update_or_create(
                        nflreadpy_name=nfl_name,
                        defaults={
                            'prizepicks_name': best_match,
                            'player_id': player_id,
                            'position': position,
                            'current_team': current_team,
                            'is_active': True,
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created mapping: {nfl_name} → {best_match} ({current_team})")
                    else:
                        updated_count += 1
                        self.stdout.write(f"Updated mapping: {nfl_name} → {best_match} ({current_team})")
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would create/update {created_count + updated_count} mappings")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} new mappings and updated {updated_count} existing mappings"))

    def find_best_match(self, nfl_name, prizepicks_players, threshold):
        """Find the best matching PrizePicks player name for an NFL player name"""
        best_match = None
        best_score = 0
        
        for pp_name in prizepicks_players:
            score = self.calculate_similarity(nfl_name, pp_name)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = pp_name
        
        return best_match

    def calculate_similarity(self, name1, name2):
        """Calculate similarity between two player names"""
        # Normalize names for better matching
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Boost score for exact last name match
        last1 = self.get_last_name(norm1)
        last2 = self.get_last_name(norm2)
        if last1 == last2 and last1:  # Ensure last name exists
            similarity += 0.3
        
        # Boost score for first name match (exact or initial)
        first1 = self.get_first_name(norm1)
        first2 = self.get_first_name(norm2)
        if first1 == first2 and first1:  # Exact first name match
            similarity += 0.2
        elif first1 and first2 and first1[0] == first2[0]:  # First initial match
            similarity += 0.1
        
        # Penalize if last names are completely different
        if last1 and last2 and last1 != last2:
            similarity *= 0.5
        
        return min(similarity, 1.0)

    def normalize_name(self, name):
        """Normalize player name for comparison"""
        if not name:
            return ""
        
        # Convert to lowercase and remove extra spaces
        normalized = re.sub(r'\s+', ' ', name.lower().strip())
        
        # Remove common suffixes
        suffixes = ['jr', 'sr', 'ii', 'iii', 'iv', 'v']
        for suffix in suffixes:
            if normalized.endswith(f' {suffix}'):
                normalized = normalized[:-len(f' {suffix}')]
        
        return normalized

    def get_last_name(self, name):
        """Extract last name from full name"""
        parts = name.split()
        return parts[-1] if parts else ""

    def get_first_name(self, name):
        """Extract first name from full name"""
        parts = name.split()
        return parts[0] if parts else ""

    def get_first_initial(self, name):
        """Extract first initial from full name"""
        parts = name.split()
        return parts[0][0] if parts and parts[0] else ""
